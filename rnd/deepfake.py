# -*- coding: utf-8 -*-
import os
import subprocess
import argparse
import torch
import sys
import requests
import shutil
import time
import numpy as np
from scipy.io import wavfile

def download_file(url, destination):
    """Download a file from URL to destination with progress tracking"""
    print(f"Downloading {url} to {destination}...")
    response = requests.get(url, stream=True)
    response.raise_for_status()  # Raise an exception for HTTP errors
    
    file_size = int(response.headers.get('content-length', 0))
    
    with open(destination, 'wb') as f:
        if file_size == 0:
            print("Warning: Content-Length header not available")
            shutil.copyfileobj(response.raw, f)
        else:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    print(f"\rDownloaded {downloaded/1024/1024:.1f} MB of {file_size/1024/1024:.1f} MB ({downloaded*100/file_size:.1f}%)", end="")
            print()  # New line after progress

def download_model(model_path):
    """Try multiple URLs to download the model"""
    model_urls = [
        "https://huggingface.co/wjj31/Wav2Lip/resolve/main/wav2lip_gan.pth",
        "https://github.com/justinjohn0306/Wav2Lip/releases/download/models/wav2lip_gan.pth",
    ]
    
    for url in model_urls:
        try:
            download_file(url, model_path)
            # Verify file size
            if os.path.getsize(model_path) > 1000000:  # 1MB minimum
                print(f"Model downloaded successfully to {model_path}")
                return True
            else:
                print(f"Downloaded file is too small ({os.path.getsize(model_path)} bytes)")
                os.remove(model_path)  # Remove the incomplete file
        except Exception as e:
            print(f"Failed to download from {url}: {e}")
    
    print("Could not download the model from any of the available sources.")
    print("Please download the model manually and place it at:", model_path)
    print("You can try downloading it from: https://huggingface.co/wjj31/Wav2Lip/resolve/main/wav2lip_gan.pth")
    return False

def read_text_from_file(file_path):
    """Read text from a file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read().strip()
        print(f"Text loaded from file: {file_path}")
        return text
    except Exception as e:
        raise ValueError(f"Error reading text file {file_path}: {e}")

def extract_audio_from_video(video_path, audio_path):
    """Extract audio from video to use as voice reference"""
    print(f"Extracting audio from video for voice cloning...")
    cmd = f"ffmpeg -y -i \"{video_path}\" -q:a 0 -map a \"{audio_path}\""
    try:
        subprocess.run(cmd, shell=True, check=True)
        print(f"Audio extracted to {audio_path}")
        return audio_path
    except subprocess.CalledProcessError as e:
        print(f"Error extracting audio: {e}")
        return None

def setup_environment():
    # Check if Wav2Lip already exists
    if not os.path.exists("Wav2Lip"):
        # Clone Wav2Lip repository
        print("Cloning Wav2Lip repository...")
        subprocess.run("git clone https://github.com/Rudrabha/Wav2Lip.git", shell=True, check=True)
    
    # Change to Wav2Lip directory
    wav2lip_dir = os.path.abspath("Wav2Lip")
    os.chdir(wav2lip_dir)
    
    # Create checkpoints directory if it doesn't exist
    os.makedirs("checkpoints", exist_ok=True)
    
    # Install required packages individually (avoiding requirements.txt issues)
    print("Installing required packages...")
    try:
        # Core dependencies
        subprocess.run("pip install numpy scipy requests tqdm opencv-python", shell=True, check=True)
        subprocess.run("pip install librosa==0.9.1 ffmpeg-python", shell=True, check=True)
        
        # Install TTS dependencies for voice cloning
        print("Installing TTS with voice cloning capability...")
        subprocess.run("pip install TTS", shell=True, check=True)
        
        # Try to install face detection dependencies
        subprocess.run("pip install face-alignment==1.3.5", shell=True, check=True)
        
    except subprocess.CalledProcessError as e:
        print(f"Warning: Some packages could not be installed: {e}")
        print("Continuing with available packages...")
    
    # Download pre-trained model
    model_path = "checkpoints/wav2lip_gan.pth"
    if not os.path.exists(model_path) or os.path.getsize(model_path) < 1000000:
        success = download_model(model_path)
        if not success:
            print("\nWARNING: Could not download the model automatically.")
            print("You'll need to download it manually and place it in the checkpoints directory.")
            print("The script will continue, but will likely fail later without the model file.")
    else:
        print(f"Using existing model file at {model_path}")
    
    return wav2lip_dir

def text_to_speech_with_voice_cloning(text, output_file, reference_audio, language='ru'):
    """Convert text to speech using TTS with voice cloning"""
    print(f"Generating speech with voice cloning...")
    
    try:
        from TTS.api import TTS
        
        # Initialize TTS with the voice cloning model
        print("Loading XTTS model for voice cloning...")
        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
        
        # Generate speech with voice cloning
        print(f"Generating speech using reference audio: {reference_audio}")
        tts.tts_to_file(text=text, 
                        file_path=output_file,
                        speaker_wav=reference_audio,
                        language=language)
        
        print(f"Speech with cloned voice saved to {output_file}")
        return output_file
        
    except Exception as e:
        print(f"Error generating speech with voice cloning: {e}")
        print("Falling back to basic TTS...")
        return text_to_speech_basic(text, output_file, language)

def text_to_speech_basic(text, output_file, language='en'):
    """Convert text to speech using gTTS (fallback)"""
    print(f"Generating speech from text in {language} using gTTS (fallback)...")
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang=language, slow=False)
        tts.save(output_file)
        print(f"Speech saved to {output_file}")
        return output_file
    except Exception as e:
        print(f"Error generating speech with gTTS: {e}")
        raise ValueError(f"Failed to generate speech: {e}")

def enhance_audio(input_audio, output_audio):
    """Enhance audio quality"""
    print(f"Enhancing audio quality...")
    cmd = f"ffmpeg -y -i \"{input_audio}\" -af 'highpass=f=50, lowpass=f=8000, loudnorm=I=-16:TP=-1.5:LRA=11' \"{output_audio}\""
    try:
        subprocess.run(cmd, shell=True, check=True)
        print(f"Enhanced audio saved to {output_audio}")
        return output_audio
    except subprocess.CalledProcessError:
        print("Warning: Audio enhancement failed. Using original audio.")
        return input_audio

def create_lipsync_deepfake(face_video, audio_file, output_path):
    """Create lip-synced deepfake using Wav2Lip"""
    print(f"Creating lip-sync deepfake...")
    print(f"Face video: {face_video}")
    print(f"Audio file: {audio_file}")
    print(f"Output path: {output_path}")
    
    # Ensure the face_video path exists
    if not os.path.exists(face_video):
        raise ValueError(f"Face video file not found: {face_video}")
    
    # Ensure the audio_file path exists
    if not os.path.exists(audio_file):
        raise ValueError(f"Audio file not found: {audio_file}")
    
    # Ensure the model file exists and has a reasonable size
    model_path = "checkpoints/wav2lip_gan.pth"
    if not os.path.exists(model_path) or os.path.getsize(model_path) < 1000000:
        raise ValueError(f"Model file is missing or corrupted: {model_path}")
    
    # Make sure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    command = f"python inference.py --checkpoint_path checkpoints/wav2lip_gan.pth --face \"{face_video}\" --audio \"{audio_file}\" --outfile \"{output_path}\" --pads 0 20 0 0 --resize_factor 1"
    print(f"Running command: {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        print("Error during lip-sync process:")
        print(result.stdout)
        print(result.stderr)
        raise RuntimeError("Wav2Lip inference failed")
    
    return output_path

def main():
    parser = argparse.ArgumentParser(description="Create a deepfake that speaks custom text with voice cloning")
    parser.add_argument("--face", required=True, help="Video with the face to animate")
    
    # Create a mutually exclusive group for text input
    text_group = parser.add_mutually_exclusive_group(required=True)
    text_group.add_argument("--text", help="Text you want the deepfake to speak")
    text_group.add_argument("--text-file", help="Path to a text file containing the text to speak")
    
    parser.add_argument("--output", required=True, help="Output video file")
    parser.add_argument("--language", default="ru", help="Language code for TTS (default: ru)")
    parser.add_argument("--reference-audio", help="Optional: Path to reference audio file for voice cloning. If not provided, audio will be extracted from the input video.")
    args = parser.parse_args()
    
    # Convert to absolute paths
    original_dir = os.getcwd()
    face_path = os.path.abspath(args.face)
    output_path = os.path.abspath(args.output)
    
    # Get text content
    if args.text:
        text_content = args.text
        print(f"Using provided text: {text_content}")
    else:
        text_file_path = os.path.abspath(args.text_file)
        text_content = read_text_from_file(text_file_path)
        print(f"Using text from file (first 100 chars): {text_content[:100]}...")
    
    print(f"Processing video: {face_path}")
    print(f"Output will be saved to: {output_path}")
    
    try:
        # Setup environment
        wav2lip_path = setup_environment()
        
        # Create temporary directory for audio files
        temp_dir = os.path.join(wav2lip_path, "temp_files")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Get reference audio for voice cloning
        if args.reference_audio:
            reference_audio = os.path.abspath(args.reference_audio)
            print(f"Using provided reference audio: {reference_audio}")
        else:
            # Extract audio from the input video
            reference_audio = os.path.join(temp_dir, "reference_audio.wav")
            extract_audio_from_video(face_path, reference_audio)
        
        # Generate speech from text with voice cloning
        temp_audio = os.path.join(temp_dir, "temp_audio.wav")
        audio_file = text_to_speech_with_voice_cloning(text_content, temp_audio, reference_audio, language=args.language)
        
        # Enhance audio quality
        enhanced_audio = os.path.join(temp_dir, "enhanced_audio.wav")
        enhanced_audio = enhance_audio(audio_file, enhanced_audio)
        
        # Create the deepfake with lip sync
        result_path = create_lipsync_deepfake(face_path, enhanced_audio, output_path)
        print(f"Deepfake created successfully at {result_path}")
        
        # Return to original directory
        os.chdir(original_dir)
        
    except Exception as e:
        print(f"Error: {e}")
        # Print more detailed traceback
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

# Usage with direct text and voice cloning from the input video:
# python deepfake.py --face "data/video.mp4" --text "Привет, это тестовое сообщение" --output "data/result.mp4"

# Usage with text file and custom reference audio:
# python deepfake.py --face "data/video.mp4" --text-file "data/speech.txt" --output "data/result.mp4" --reference-audio "data/voice_sample.wav"