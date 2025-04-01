# -*- coding: utf-8 -*-
import os
import subprocess
import argparse
import torch
from gtts import gTTS
import sys

def setup_environment():
    # Check if Wav2Lip already exists
    if not os.path.exists("Wav2Lip"):
        # Clone Wav2Lip repository
        subprocess.run("git clone https://github.com/Rudrabha/Wav2Lip.git", shell=True, check=True)
    
    # Change to Wav2Lip directory
    wav2lip_dir = os.path.abspath("Wav2Lip")
    os.chdir(wav2lip_dir)
    
    # Create checkpoints directory if it doesn't exist
    os.makedirs("checkpoints", exist_ok=True)
    
    # Install requirements if needed
    if not os.path.exists("checkpoints/wav2lip_gan.pth"):
        # Install requirements - fixing the installation order
        subprocess.run("pip install numpy scipy", shell=True, check=True)
        subprocess.run("pip install librosa==0.9.1 opencv-python ffmpeg-python gTTS transformers", shell=True, check=True)
        subprocess.run("pip install -r requirements.txt", shell=True, check=True)
        
        # Download pre-trained model
        subprocess.run("wget 'https://github.com/Rudrabha/Wav2Lip/releases/download/v1.0/wav2lip_gan.pth' -O checkpoints/wav2lip_gan.pth", shell=True, check=True)
    
    return wav2lip_dir

def text_to_speech(text, output_file, language='en'):
    """Convert text to speech using gTTS"""
    print(f"Generating speech from text in {language}...")
    tts = gTTS(text=text, lang=language, slow=False)
    tts.save(output_file)
    print(f"Speech saved to {output_file}")
    return output_file

def enhance_audio(input_audio, output_audio):
    """Optional: Enhance audio quality"""
    print(f"Enhancing audio quality...")
    cmd = f"ffmpeg -y -i {input_audio} -af 'highpass=f=200, lowpass=f=3000' {output_audio}"
    subprocess.run(cmd, shell=True, check=True)
    print(f"Enhanced audio saved to {output_audio}")
    return output_audio

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
    
    command = f"python inference.py --checkpoint_path checkpoints/wav2lip_gan.pth --face '{face_video}' --audio '{audio_file}' --outfile '{output_path}' --pads 0 20 0 0"
    print(f"Running command: {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        print("Error during lip-sync process:")
        print(result.stdout)
        print(result.stderr)
        raise RuntimeError("Wav2Lip inference failed")
    
    return output_path

def main():
    parser = argparse.ArgumentParser(description="Create a deepfake that speaks custom text")
    parser.add_argument("--face", required=True, help="Video with the face to animate")
    parser.add_argument("--text", required=True, help="Text you want the deepfake to speak")
    parser.add_argument("--output", required=True, help="Output video file")
    parser.add_argument("--language", default="en", help="Language code for TTS (default: en)")
    args = parser.parse_args()
    
    # Convert to absolute paths
    original_dir = os.getcwd()
    face_path = os.path.abspath(args.face)
    output_path = os.path.abspath(args.output)
    
    # Setup environment
    wav2lip_path = setup_environment()
    
    # Create temporary directory for audio files
    temp_dir = os.path.join(wav2lip_path, "temp_files")
    os.makedirs(temp_dir, exist_ok=True)
    
    # Generate speech from text
    temp_audio = os.path.join(temp_dir, "temp_audio.wav")
    audio_file = text_to_speech(args.text, temp_audio, language=args.language)
    
    # Optional: enhance audio quality
    enhanced_audio = os.path.join(temp_dir, "enhanced_audio.wav")
    enhanced_audio = enhance_audio(audio_file, enhanced_audio)
    
    # Create the deepfake with lip sync
    try:
        result_path = create_lipsync_deepfake(face_path, enhanced_audio, output_path)
        print(f"Deepfake created successfully at {result_path}")
    except Exception as e:
        print(f"Error creating deepfake: {e}")
        sys.exit(1)
    
    # Return to original directory
    os.chdir(original_dir)

if __name__ == "__main__":
    main()

# Usage:
# python deepfake.py --face "data/popidka_2.mp4" --text "Привет я Лариса Гузеева" --output "data/deepfake_result.mp4" --language "ru"