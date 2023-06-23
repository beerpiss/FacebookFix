import aiohttp
import json
import re

import sanic
from sanic import Sanic, redirect, Request, HTTPResponse, BadRequest


UA_REGEX = re.compile(r"bot|facebook|embed|got|firefox\/92|firefox\/38|curl|wget|go-http|yahoo|generator|whatsapp|preview|link|proxy|vkshare|images|analyzer|index|crawl|spider|python|cfnetwork|node") 
REEL_DATA_REGEX = re.compile(r"\(ScheduledApplyEach,({\"define\":\[\[\"VideoPlayerShakaPerformanceLoggerConfig\".+?)\);") 
headers = {
    "authority": "www.facebook.com",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
    "accept-language": "en-US,en;q=0.9",
    "cache-control": "max-age=0",
    "sec-fetch-mode": "navigate",
    "upgrade-insecure-requests": "1",
    "referer": "https://www.facebook.com/",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.60 Safari/537.36",
    "viewport-width": "1280",
}
app = Sanic(__name__)

@app.listener("before_server_start")
def init(app, loop):
    app.ctx.session = aiohttp.ClientSession(loop=loop, headers=headers)

@app.listener("after_server_stop")
def finish(app, loop):
    loop.run_until_complete(app.ctx.session.close())
    loop.close()

@app.get("oembed.json")
async def oembed(request: "Request") -> "HTTPResponse":
    id = request.args.get("id")
    if not id:
        raise BadRequest

    post_url = f"https://facebook.com/reel/{id}"

    async with app.ctx.session.get(post_url) as resp:
        if not resp.ok:
            return redirect(post_url)
        resp_text = await resp.text()
    
    data = REEL_DATA_REGEX.search(resp_text)
    if not data:
        raise BadRequest
    
    data = json.loads(data.group(1))

    stream_cache = next((x for x in data["require"] if x[0] == "RelayPrefetchedStreamCache"), None)
    if not stream_cache:
        raise BadRequest
    
    result = stream_cache[3][1]["__bbox"]["result"]
    creation_story = result["data"]["video"]["creation_story"]
    short_form_video_context = creation_story["short_form_video_context"]
    return sanic.json(
        {
            "author_name": short_form_video_context["video_owner"]["name"],
            "author_url": post_url,
            "provider_name": "FacebookFix",
            "provider_url": "",
            "title": "Facebook",
            "type": "link",
            "version": "1.0",
        }
    )


@app.get("/reel/<id:int>")
@app.ext.template("base.html")
async def reel(request: "Request", id: int): 
    post_url = f"https://facebook.com/reel/{id}"
    if not UA_REGEX.search(request.headers.get("User-Agent", ""), re.IGNORECASE):
        return redirect(post_url)
    
    async with app.ctx.session.get(post_url) as resp:
        if not resp.ok:
            return redirect(post_url)
        resp_text = await resp.text()
    
    data = REEL_DATA_REGEX.search(resp_text)
    if not data:
        return redirect(post_url)
    
    data = json.loads(data.group(1))
    
    stream_cache = next((x for x in data["require"] if x[0] == "RelayPrefetchedStreamCache"), None)
    if not stream_cache:
        return redirect(post_url)
    
    result = stream_cache[3][1]["__bbox"]["result"]
    creation_story = result["data"]["video"]["creation_story"]
    short_form_video_context = creation_story["short_form_video_context"]

    all_qualities = sorted(
        result["extensions"]["all_video_dash_prefetch_representations"][0]["representations"],
        key=lambda x: x["width"]
    )
    best_quality = all_qualities[-1]
    
    return {
        "id": id,
        "card": "player",
        "title": short_form_video_context["video_owner"]["name"],
        "url": post_url,
        "description": creation_story["message"]["text"],
        "video": best_quality["base_url"],
        "width": best_quality["width"],
        "height": best_quality["height"],
    }



    


    
    

