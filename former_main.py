from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
import requests
import uvicorn
import json
import re
import os

port = int(os.environ.get('PORT', 8080))
app = FastAPI(docs_url=None, redoc_url=None)

def find_embed_url(text):
	match = re.search(r"EMBED_VIDEO_FILE = '([^']*)'", text)
	return match.group(1) if match else None

def find_hls_stream(text):
	match = re.search(r'"hlsManifestUrl":".*\.m3u8', text)
	return match.group(0)[:-1] if match else None

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
	return PlainTextResponse(str(exc.detail), status_code=exc.status_code)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
	return PlainTextResponse(str(exc), status_code=status.HTTP_400_BAD_REQUEST)

@app.get("/dwls/", status_code=status.HTTP_200_OK)
async def handle_dwls(request: Request):
	try:
		dwls_url = "https://www.gmanetwork.com/radio/streaming/dwls"
		dwls_response = requests.get(dwls_url, headers={"Cache-Control": "no-cache"})
		dwls_response.raise_for_status()

		if not dwls_response.status_code == 200:
			raise ValueError(f"Failed to fetch DWLS URL: {dwls_response.status_code}")

		stream_url = find_embed_url(dwls_response.text)

		if stream_url:
			youtube_url = f"https://www.youtube.com/live/{stream_url}"

			response = requests.get(youtube_url, headers={"Cache-Control": "no-cache"})
			response.raise_for_status()

			if not response.status_code == 200:
				raise ValueError(f"Failed to fetch YouTube URL: {response.status_code}")

			text = response.text
			manifest_url = json.loads('{' + f"{find_hls_stream(text)}" + '"}')

			if manifest_url:
				return RedirectResponse(manifest_url["hlsManifestUrl"], status_code=302)
			else:
				raise ValueError("HLS stream URL not found in the manifest response.")
		else:
			raise ValueError("Embed URL not found in the Streaming Page for DWLS.")

	except Exception as e:
		return Response(str(e.args), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@app.get("/dzbb/", status_code=status.HTTP_200_OK)
async def handle_dzbb(request: Request):
	try:
		dwls_url = "https://www.gmanetwork.com/radio/streaming/dzbb"
		dwls_response = requests.get(dwls_url, headers={"Cache-Control": "no-cache"})
		dwls_response.raise_for_status()

		if not dwls_response.status_code == 200:
			raise ValueError(f"Failed to fetch DZBB URL: {dwls_response.status_code}")

		stream_url = find_embed_url(dwls_response.text)

		if stream_url:
			youtube_url = f"https://www.youtube.com/live/{stream_url}"

			response = requests.get(youtube_url, headers={"Cache-Control": "no-cache"})
			response.raise_for_status()

			if not response.status_code == 200:
				raise ValueError(f"Failed to fetch YouTube URL: {response.status_code}")

			text = response.text
			manifest_url = json.loads('{' + f"{find_hls_stream(text)}" + '"}')

			if manifest_url:
				return RedirectResponse(manifest_url["hlsManifestUrl"], status_code=302)
			else:
				raise ValueError("HLS stream URL not found in the response")
		else:
			raise ValueError("Embed URL not found in the Streaming Page for DZBB.")

	except Exception as e:
		return Response(str(e.args), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

# This section is for development purposes only. Remove before deployment.
if __name__ == "__main__":
  	uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True, workers=1)
