import os,hmac,shutil,tempfile,subprocess,wave,re
import urllib.request,urllib.error
from xml.sax.saxutils import escape
from pathlib import Path
from fastapi import FastAPI,HTTPException,Header
from fastapi.responses import FileResponse
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel,Field
from PIL import Image,ImageDraw,ImageFont
from starlette.background import BackgroundTask

app=FastAPI(title="Tech Talks with Manju Shorts renderer")
W,H=540,960
FONT="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
class Short(BaseModel):
    topic:str=Field(min_length=3,max_length=140)
    title:str=Field(min_length=3,max_length=110)
    voiceover:str=Field(min_length=45,max_length=850)
    brand:str=Field(default="Tech Talks with Manju",max_length=60)
def font(sz,bold=False):
    return ImageFont.truetype(BOLD if bold else FONT,sz)
def wrapped(draw,txt,ft,maxw):
    result=[];current=""
    for word in txt.split():
        trial=(current+" "+word).strip()
        if draw.textbbox((0,0),trial,font=ft)[2]<maxw:current=trial
        else:
            if current:result.append(current)
            current=word
    if current:result.append(current)
    return result
# Version 2: light-weight themed explainer visuals with a vector cartoon presenter.
# No extra Python packages, assets, GPU or changes to the existing n8n request body.
THEMES={
 "ai":((24,36,78),(95,133,235),(119,220,255)),
 "automation":((13,53,53),(30,151,124),(157,245,205)),
 "cloud":((19,46,75),(73,141,199),(182,227,255)),
 "security":((68,30,54),(184,76,107),(255,191,206)),
 "data":((35,41,83),(125,107,200),(224,201,255)),
 "creative":((72,43,43),(221,136,82),(255,222,160)),
 "learning":((29,55,76),(72,177,184),(177,242,240))
}
def pick_theme(topic,idx):
    t=topic.lower()
    if any(x in t for x in ["n8n","workflow","trigger","webhook","automation","oauth","api"]):base="automation"
    elif any(x in t for x in ["cloud","azure","server","network","infrastructure"]):base="cloud"
    elif any(x in t for x in ["security","privacy","injection","guardrail","jailbreak"]):base="security"
    elif any(x in t for x in ["data","vector","embedding","search","rag","database"]):base="data"
    elif any(x in t for x in ["image","video","voice","speech","multimodal","diffusion"]):base="creative"
    elif any(x in t for x in ["model","llm","neural","machine learning","ai agent","artificial intelligence"]):base="ai"
    else:base="learning"
    names=list(THEMES)
    if idx%4==2:base=names[(names.index(base)+1)%len(names)]
    return base,THEMES[base]
def cartoon(d,anchor,pose="explain",scale=1.0):
    x,y=anchor
    def p(v):return int(v*scale)
    skin=(245,186,139);shirt=(30,99,178);dark=(20,39,63)
    # Body, arms and collar. Presenter is a deliberately simple cartoon, not a talking avatar.
    d.rounded_rectangle((x-p(61),y+p(92),x+p(72),y+p(256)),radius=p(23),fill=shirt,outline=(162,225,254),width=3)
    d.polygon([(x-p(10),y+p(91)),(x+p(14),y+p(91)),(x+p(3),y+p(125))],fill=(240,242,247))
    d.line([(x-p(50),y+p(139)),(x-p(86),y+p(196)),(x-p(69),y+p(220))],fill=skin,width=max(6,p(18)))
    if pose=="point":
        d.line([(x+p(64),y+p(143)),(x+p(102),y+p(88)),(x+p(133),y+p(61))],fill=skin,width=max(6,p(18)))
        d.ellipse((x+p(125),y+p(47),x+p(143),y+p(75)),fill=skin)
    elif pose=="think":
        d.line([(x+p(62),y+p(145)),(x+p(92),y+p(124)),(x+p(66),y+p(67))],fill=skin,width=max(6,p(18)))
    else:
        d.line([(x+p(61),y+p(141)),(x+p(108),y+p(176)),(x+p(132),y+p(159))],fill=skin,width=max(6,p(18)))
        d.ellipse((x+p(121),y+p(148),x+p(147),y+p(174)),fill=skin)
    d.ellipse((x-p(47),y-p(25),x+p(49),y+p(93)),fill=skin,outline=(93,69,76),width=3)
    d.pieslice((x-p(49),y-p(39),x+p(53),y+p(41)),180,360,fill=dark)
    d.ellipse((x-p(24),y+p(32),x-p(16),y+p(42)),fill=dark)
    d.ellipse((x+p(17),y+p(32),x+p(25),y+p(42)),fill=dark)
    d.arc((x-p(16),y+p(43),x+p(19),y+p(68)),5,170,fill=(122,57,65),width=3)
PRESENTER_ATLAS=Path(__file__).parent/'assets'/'presenter_atlas.webp'
from visuals_v3 import render_slide_v3, split_voiceover

def slide_v3(path,headline,copy,brand,idx,total,topic):
    return render_slide_v3(path,headline,copy,brand,idx,total,topic,
                           PRESENTER_ATLAS,pick_theme,font,W,H)

def slide(path,headline,copy,brand,idx,total,topic=""):
    if PRESENTER_ATLAS.is_file():
        return slide_v3(path,headline,copy,brand,idx,total,topic)
    theme,(base,mid,bright)=pick_theme(topic or headline,idx)
    im=Image.new("RGB",(W,H));d=ImageDraw.Draw(im)
    # Distinct palette + alternating layouts, designed for narrow-screen readability.
    for y in range(H):
        k=y/H
        rgb=tuple(int(base[i]*(1-k)+mid[i]*k*.54) for i in range(3))
        d.line((0,y,W,y),fill=rgb)
    for y in range(125,860,92):
        d.line((20,y,W-20,y),fill=tuple(min(255,z+17) for z in base),width=1)
    d.ellipse((W-165,-82,W+95,170),outline=bright,width=5)
    d.rounded_rectangle((18,25,W-18,95),radius=15,fill=base,outline=bright,width=2)
    b=brand.upper();ft=font(18,True)
    while d.textbbox((0,0),b,font=ft)[2]>W-48 and len(b)>10:b=b[:-2]
    d.text((30,50),b,font=ft,fill=(247,250,255))
    label=headline.upper()[:34]
    d.rounded_rectangle((26,135,W-26,214),radius=20,fill=mid)
    d.text((43,157),label,font=font(23,True),fill=(255,255,255))
    is_intro=(idx==0);is_end=(idx==total-1)
    top=275 if idx%2==0 else 260
    bottom=645 if idx%2==0 else 630
    d.rounded_rectangle((22,top,W-22,bottom),radius=25,fill=(241,249,252),outline=bright,width=4)
    # Draw a topic-specific concept icon or explanatory flow, not identical slides.
    if theme=="automation":
        for j in range(3):
            xx=62+j*150
            d.rounded_rectangle((xx,top+28,xx+104,top+90),radius=12,fill=mid)
            d.text((xx+20,top+48),["GO","DO","DONE"][j],font=font(18,True),fill=(255,255,255))
            if j<2:d.line((xx+106,top+58,xx+143,top+58),fill=mid,width=5)
    elif theme=="data":
        for j,h in enumerate([35,60,82,51]):
            xx=112+j*83
            d.rounded_rectangle((xx,bottom-40-h,xx+43,bottom-40),radius=7,fill=mid)
    elif theme=="security":
        d.polygon([(W//2,top+35),(W//2+43,top+53),(W//2+33,top+116),(W//2,top+139),(W//2-33,top+116),(W//2-43,top+53)],fill=mid)
    elif theme=="cloud":
        for j in range(3):
            xx=126+j*105
            d.rounded_rectangle((xx,top+32,xx+76,top+68),radius=9,fill=mid)
    elif theme=="creative":
        d.rounded_rectangle((W//2-62,top+25,W//2+62,top+109),radius=14,outline=mid,width=7)
        d.polygon([(W//2-13,top+42),(W//2-13,top+94),(W//2+28,top+67)],fill=mid)
    else:
        for j in range(3):
            xx=134+j*68
            d.ellipse((xx,top+43,xx+38,top+81),fill=mid)
            if j<2:d.line((xx+38,top+62,xx+68,top+62),fill=mid,width=4)
    text=copy.replace("\n"," ").strip()
    max_width=W-105
    for sz in (31,28,25,22,19,17):
        ff=font(sz,True)
        lines=wrapped(d,text,ff,max_width)
        if len(lines)*int(sz*1.38)<=160:break
    yy=top+152
    for line in lines[:7]:
        tw=d.textbbox((0,0),line,font=ff)[2]
        d.text(((W-tw)/2,yy),line,font=ff,fill=(20,39,62))
        yy+=int(sz*1.38)
    pose="point" if idx%3==0 else ("think" if idx%3==1 else "explain")
    cartoon(d,(104,677),pose=pose,scale=.63)
    d.rounded_rectangle((214,705,510,840),radius=16,fill=base,outline=bright,width=3)
    tip= "LET'S EXPLORE!" if is_intro else ("FOLLOW FOR MORE" if is_end else ["WATCH THE CONNECTION","HERE'S THE IDEA","PUT IT TO WORK"][idx%3])
    d.text((231,746),tip,font=font(17,True),fill=(255,255,255))
    d.rounded_rectangle((32,885,W-32,892),radius=3,fill=base)
    d.rounded_rectangle((32,885,32+int((W-64)*(idx+1)/max(1,total)),892),radius=3,fill=bright)
    d.text((36,915),"AI • AUTOMATION • EXPLAINED",font=font(14,True),fill=(241,250,255))
    im.save(path)
# Azure Speech F0 neural TTS is enabled when its key and region are configured.
# Without those variables, the original free eSpeak NG path remains available.
def synthesize_speech(text,wav):
    key=os.environ.get("AZURE_SPEECH_KEY","").strip()
    region=os.environ.get("AZURE_SPEECH_REGION","").strip().lower()
    if bool(key)!=bool(region):
        raise ValueError("Set both AZURE_SPEECH_KEY and AZURE_SPEECH_REGION, or neither")
    if key:
        if not re.fullmatch(r"[a-z0-9-]{2,32}",region):
            raise ValueError("Invalid AZURE_SPEECH_REGION")
        voice=os.environ.get("AZURE_SPEECH_VOICE","en-IN-ArjunNeural").strip()
        allowed={"en-IN-ArjunNeural","en-IN-PrabhatNeural","en-IN-AaravNeural","en-IN-RehaanNeural","en-IN-KunalNeural"}
        if voice not in allowed:
            raise ValueError("Unsupported AZURE_SPEECH_VOICE")
        text_xml=escape(text)
        ssml=("<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-IN'>"
              f"<voice name='{voice}'>{text_xml}</voice></speak>")
        headers={"Ocp-Apim-Subscription-Key":key,
                 "Content-Type":"application/ssml+xml; charset=utf-8",
                 "X-Microsoft-OutputFormat":"riff-24khz-16bit-mono-pcm",
                 "User-Agent":"TechTalksShortsRenderer"}
        request=urllib.request.Request(
            f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
            data=ssml.encode("utf-8"),headers=headers,method="POST")
        try:
            with urllib.request.urlopen(request,timeout=75) as response:
                content=response.read()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Azure Speech request failed (HTTP {exc.code}). Check region, Speech F0 resource, and key.") from None
        except urllib.error.URLError:
            raise RuntimeError("Azure Speech connection failed. Check region/network and try again.") from None
        if not content.startswith(b"RIFF"):
            raise RuntimeError("Azure Speech did not return WAV/RIFF audio")
        wav.write_bytes(content)
        return "azure-neural"
    speech=subprocess.run(["espeak-ng","-v","en-in+m3","-s","144","-w",str(wav),text],capture_output=True,timeout=100)
    if speech.returncode:
        raise RuntimeError(speech.stderr.decode(errors="replace")[-400:])
    return "espeak-ng"

def generate(data,tmp):
    wav=tmp/"narration.wav"
    synthesize_speech(data.voiceover,wav)
    with wave.open(str(wav),"rb") as a:duration=a.getnframes()/a.getframerate()
    if not 8<=duration<=160:raise ValueError("Narration must be between 8 and 160 seconds")
    words=data.voiceover.strip().split();sections=split_voiceover(data.voiceover)
    word_total=sum(len(s.split()) for s in sections)
    slides=[("TODAY'S TOPIC",data.topic,1.4)]
    for i,part in enumerate(sections):slides.append((f"POINT {i+1} OF {len(sections)}",part,(duration-1.4)*len(part.split())/word_total))
    slides.append(("FOLLOW FOR MORE","Practical AI and automation tutorials.",1.4))
    concat=["ffconcat version 1.0"]
    for i,(heading,txt,length) in enumerate(slides):
        name=f"slide_{i:02d}.png";slide(tmp/name,heading,txt,data.brand,i,len(slides),data.topic)
        concat.extend([f"file '{name}'",f"duration {length:.4f}"])
    concat.append(f"file 'slide_{len(slides)-1:02d}.png'")
    (tmp/"slides.txt").write_text("\n".join(concat)+"\n")
    output=tmp/"short.mp4"
    cmd=["ffmpeg","-hide_banner","-loglevel","error","-y","-threads","1","-safe","0","-f","concat","-i",str(tmp/"slides.txt"),"-i",str(wav),"-t",f"{duration+1.4:.2f}","-vf","fps=4,format=yuv420p","-c:v","libx264","-preset","ultrafast","-crf","33","-threads","1","-c:a","aac","-b:a","48k","-af","apad","-movflags","+faststart",str(output)]
    p=subprocess.run(cmd,cwd=tmp,capture_output=True,timeout=800)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors="replace")[-800:])
    return output
@app.get("/health")
def health():
    return {"status":"ok","renderer":"ffmpeg-cloud-shorts-v3-layout2" if PRESENTER_ATLAS.is_file() else "ffmpeg-cloud-shorts-v2","tts":"azure-neural" if os.environ.get("AZURE_SPEECH_KEY") and os.environ.get("AZURE_SPEECH_REGION") else "espeak-ng","format":"540x960 mp4"}
@app.post("/render")
async def render(data:Short,x_render_key:str|None=Header(None)):
    secret=os.environ.get("RENDER_SECRET")
    if not secret:raise HTTPException(503,"Set RENDER_SECRET in Render environment")
    if not x_render_key or not hmac.compare_digest(x_render_key,secret):raise HTTPException(401,"Unauthorized")
    folder=Path(tempfile.mkdtemp(prefix="short_"))
    try:video=await run_in_threadpool(generate,data,folder)
    except Exception as exc:
        shutil.rmtree(folder,ignore_errors=True)
        raise HTTPException(422,str(exc)[:650])
    return FileResponse(video,media_type="video/mp4",filename="short.mp4",background=BackgroundTask(shutil.rmtree,folder,ignore_errors=True))
