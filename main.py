from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import PlainTextResponse, RedirectResponse, JSONResponse
from fastapi import FastAPI, Request, status, HTTPException
from fastapi.exceptions import RequestValidationError
import httpx
import uvicorn
import json
import re
import os

PORT = int(os.environ.get('PORT', 8080))
APP_VERSION = "1.0.0" # Example, can be dynamic

BASE_HEADERS = {
    "Cache-Control": "no-cache",
    "User-Agent": f"RadioStreamService/{APP_VERSION} (compatible; httpx/0.2x.x)"
}

app = FastAPI(docs_url=None, redoc_url=None)

def find_embed_video_id(html_content: str) -> str | None:
    match = re.search(r"EMBED_VIDEO_FILE\s*=\s*'([^']*)'", html_content)
    return match.group(1) if match else None

def find_hls_manifest_url(html_content: str) -> str | None:
    match = re.search(r'"hlsManifestUrl"\s*:\s*"([^"]*\.m3u8[^"]*)"', html_content)
    if match:
        return match.group(1).replace("\\/", "/")
    return None

@app.exception_handler(StarletteHTTPException)
async def custom_starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
    return PlainTextResponse(str(exc.detail), status_code=exc.status_code)

@app.exception_handler(RequestValidationError)
async def custom_validation_exception_handler(request: Request, exc: RequestValidationError):
    return PlainTextResponse(str(exc), status_code=status.HTTP_400_BAD_REQUEST)

async def fetch_station_stream_url(station_code: str, station_name: str) -> str:
    gma_base_url = "https://www.gmanetwork.com/radio/streaming/"
    station_url = f"{gma_base_url}{station_code}"

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        try:
            gma_response = await client.get(station_url, headers=BASE_HEADERS)
            gma_response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to fetch streaming page for {station_name} from GMA: {e.response.status_code}"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Network error while contacting GMA for {station_name}: {str(e)}"
            )

        video_id = find_embed_video_id(gma_response.text)
        if not video_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Could not find YouTube video ID for {station_name} on GMA page."
            )

        youtube_live_url = f"https://www.youtube.com/live/{video_id}"
        
        try:
            yt_response = await client.get(youtube_live_url, headers=BASE_HEADERS)
            yt_response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to fetch YouTube live page for {station_name}: {e.response.status_code}"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Network error while contacting YouTube for {station_name}: {str(e)}"
            )

        hls_url = find_hls_manifest_url(yt_response.text)
        if not hls_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"HLS stream URL not found in YouTube response for {station_name}."
            )
        
        return hls_url

@app.get("/dwls/", status_code=status.HTTP_302_FOUND)
async def handle_dwls_redirect(request: Request):
    try:
        hls_stream_url = await fetch_station_stream_url("dwls", "DWLS")
        return RedirectResponse(url=hls_stream_url, status_code=status.HTTP_302_FOUND)
    except HTTPException:
        raise 
    except Exception as e:
        # Fallback for truly unexpected errors
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred processing the DWLS request.")


@app.get("/dzbb/", status_code=status.HTTP_302_FOUND)
async def handle_dzbb_redirect(request: Request):
    try:
        hls_stream_url = await fetch_station_stream_url("dzbb", "DZBB")
        return RedirectResponse(url=hls_stream_url, status_code=status.HTTP_302_FOUND)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred processing the DZBB request.")

@app.get("/", status_code=status.HTTP_200_OK)
async def health_check():
    return {"status": "ok", "message": "API is running healthily."}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True, workers=1)
