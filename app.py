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
def slide(path,headline,copy,brand,idx,total):
    im=Image.new("RGB",(W,H));d=ImageDraw.Draw(im)
    for y in range(H):
        q=y/H;d.line((0,y,W,y),fill=(int(9+8*q),int(22+18*q),int(40+35*q)))
    for x in range(24,W,70):d.line((x,125,x,880),fill=(26,50,69))
    for y in range(145,900,70):d.line((20,y,W-20,y),fill=(26,50,69))
    d.rounded_rectangle((18,28,W-18,95),radius=15,fill=(10,55,74),outline=(34,191,222),width=2)
    b=brand.upper();brf=font(19,True)
    while d.textbbox((0,0),b,font=brf)[2]>W-52 and len(b)>8:b=b[:-2]
    d.text((30,51),b,font=brf,fill=(224,251,255))
    d.rounded_rectangle((22,215,W-22,755),radius=24,fill=(12,33,54),outline=(36,175,203),width=3)
    d.text((43,259),headline.upper(),font=font(17,True),fill=(62,226,236))
    for size in (39,35,31,27,24,21,19):
        ft=font(size,True);lines=wrapped(d,copy.replace("\n"," "),ft,W-84)
        if len(lines)*int(size*1.35)<385:break
    yy=368-len(lines)*int(size*1.35)/3
    for line in lines:
        tw=d.textbbox((0,0),line,font=ft)[2]
        d.text(((W-tw)/2,yy),line,font=ft,fill=(242,251,255));yy+=int(size*1.35)
    d.rounded_rectangle((45,814,W-45,821),radius=3,fill=(31,80,100))
    d.rounded_rectangle((45,814,45+int((W-90)*(idx+1)/total),821),radius=3,fill=(34,226,239))
    d.text((45,847),"AUTOMATE  •  LEARN  •  BUILD",font=font(14,True),fill=(142,226,234))
    d.text((45,900),"#Shorts   #n8n   #Automation",font=font(14),fill=(202,220,231))
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
    words=data.voiceover.strip().split();sections=[" ".join(words[i:i+13]) for i in range(0,len(words),13)]
    word_total=sum(len(s.split()) for s in sections)
    slides=[("TODAY'S TOPIC",data.topic,1.4)]
    for i,part in enumerate(sections):slides.append((f"POINT {i+1} OF {len(sections)}",part,(duration-1.4)*len(part.split())/word_total))
    slides.append(("FOLLOW FOR MORE","Practical AI and automation tutorials.",1.4))
    concat=["ffconcat version 1.0"]
    for i,(heading,txt,length) in enumerate(slides):
        name=f"slide_{i:02d}.png";slide(tmp/name,heading,txt,data.brand,i,len(slides))
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
    return {"status":"ok","renderer":"ffmpeg-cloud-shorts","tts":"azure-neural" if os.environ.get("AZURE_SPEECH_KEY") and os.environ.get("AZURE_SPEECH_REGION") else "espeak-ng","format":"540x960 mp4"}
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
