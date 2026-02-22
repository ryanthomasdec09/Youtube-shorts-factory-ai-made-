import os
import subprocess
import asyncio
import random
import sys
import datetime
import shutil
import re
from yt_dlp import YoutubeDL
from edge_tts import Communicate

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
ENDING_IMAGE = os.path.join(BASE_DIR, "ending.png") 
VOICE = "en-US-AriaNeural"
SEGMENT_LEN = 10 

def cleanup_workspace():
    print("\n🧹 [SYSTEM] Cleaning workspace...")
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR)
    for f in os.listdir(BASE_DIR):
        if f.startswith("temp_") or f.endswith(".mp3") or f.startswith("master_"):
            try: os.remove(os.path.join(BASE_DIR, f))
            except: pass
    print("✨ Ready to build.")

async def generate_voice(text, filename):
    # Boss requested: Ignore '#' in narration for natural speech
    clean_text = re.sub(r'#', '', text)
    communicate = Communicate(clean_text, VOICE)
    await communicate.save(filename)

def download_video(url, index):
    filename = f"master_{index}.mp4"
    print(f"\n📡 [DOWNLOADING] Source #{index+1}...")
    ydl_opts = {
        'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]',
        'outtmpl': filename, 
        'quiet': True
    }
    try:
        with YoutubeDL(ydl_opts) as ydl: ydl.download([url])
        return filename
    except Exception as e:
        print(f"❌ Download Error: {e}")
        return None

def process_slice(master_file, start_time, rank, is_first):
    clip_name = f"temp_v_{rank}.mp4"
    rank_voice = f"rank_voice_{rank}.mp3"
    # Added thick border to 'RANK' text for better visibility on Shorts
    drawtext = f"drawtext=text='RANK {rank}':fontcolor=white:fontsize=130:fontfile='C\\:/Windows/Fonts/arialbd.ttf':x=(w-text_w)/2:y=400:borderw=12:bordercolor=black:enable='between(t,0,3)'"
    
    if is_first:
        f_comp = "[1:a]volume=2.0[intro];[2:a]volume=2.0[rnk];[0:a]volume=0.5,aresample=44100[bg];[intro][rnk][bg]amix=inputs=3:duration=first[outa]"
        inputs = ['-ss', str(start_time), '-t', str(SEGMENT_LEN), '-i', master_file, '-i', 'intro.mp3', '-i', rank_voice]
    else:
        f_comp = "[1:a]volume=2.0[rnk];[0:a]volume=0.5,aresample=44100[bg];[rnk][bg]amix=inputs=2:duration=first[outa]"
        inputs = ['-ss', str(start_time), '-t', str(SEGMENT_LEN), '-i', master_file, '-i', rank_voice]
    
    cmd = ['ffmpeg', '-y'] + inputs + ['-filter_complex', f_comp, '-vf', f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1,{drawtext}", '-map', '0:v:0', '-map', '[outa]', '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '22', '-c:a', 'aac', '-ar', '44100', clip_name]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    return clip_name

async def main():
    print("\n" + "█"*60 + "\n🚀 RYAN'S VIDEO ENGINE V9.5 (MANUAL UPLOAD EDITION)\n" + "█"*60)

    cleanup_workspace()

    # Inputs
    raw_links = input("\n🔗 [INPUT] YouTube URLs (comma separated): ")
    links = [l.strip() for l in raw_links.split(",")]
    video_title = input("🎙️ [INPUT] Video Title: ")
    num_vids = int(input("🔢 [INPUT] How many variations to generate? "))
    
    # 1. DOWNLOAD
    masters = []
    for i, link in enumerate(links):
        m_file = download_video(link, i)
        if m_file:
            dur_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', m_file]
            dur = float(subprocess.run(dur_cmd, stdout=subprocess.PIPE, text=True).stdout)
            masters.append({'file': m_file, 'dur': dur})

    if not masters:
        print("❌ No videos downloaded. Exiting.")
        return

    # 2. VOICE GENERATION
    print("\n🎙️ Generating Narration...")
    await generate_voice(f"Here are the {video_title}.", "intro.mp3")
    for r in range(1, 6):
        await generate_voice(f"Number {r}", f"rank_voice_{r}.mp3")

    # 3. PRODUCTION
    for v in range(num_vids):
        output_file = os.path.join(OUTPUT_DIR, f"final_render_{v+1}.mp4")
        print(f"\n🔨 Rendering Video #{v+1}...")
        
        final_clips = []
        for r_idx in range(5):
            rank_num = 5 - r_idx
            source = random.choice(masters)
            start = random.randint(5, int(source['dur']) - SEGMENT_LEN - 5)
            final_clips.append(process_slice(source['file'], start, rank_num, (r_idx == 0)))
            
        # Ending Card
        print("🖼️ Processing Blur Ending...")
        blur = "split[main][back];[back]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:10[blurred];[main]scale=1080:1920:force_original_aspect_ratio=decrease[scaled];[blurred][scaled]overlay=(W-w)/2:(H-h)/2,fps=30"
        subprocess.run(['ffmpeg', '-y', '-loop', '1', '-i', ENDING_IMAGE, '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono', '-vf', blur, '-t', '5', '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '44100', '-shortest', 'temp_e.mp4'], stdout=subprocess.DEVNULL)
        final_clips.append('temp_e.mp4')

        # Final Stitch
        print("🪡 Stitching Final Master...")
        inputs = []
        for c in final_clips: inputs.extend(['-i', c])
        stitch = ['ffmpeg', '-y'] + inputs + ['-filter_complex', f"{''.join([f'[{i}:v][{i}:a]' for i in range(6)])}concat=n=6:v=1:a=1[v][a]", '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '22', '-c:a', 'aac', '-ar', '44100', output_file]
        subprocess.run(stitch, stdout=subprocess.DEVNULL)
        
        # Cleanup clips for this variation
        for f in final_clips: 
            if os.path.exists(f): os.remove(f)

    print("\n" + "█"*60 + f"\n🎯 DONE! Check the '/output' folder for your {num_vids} videos.\n" + "█"*60)

if __name__ == "__main__":
    asyncio.run(main())