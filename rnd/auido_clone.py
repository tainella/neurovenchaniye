import os
import torch
import torchaudio
from pydub import AudioSegment
from moviepy.editor import VideoFileClip
from wunjo import WunjoTTS

# 1. Получение голоса из видео с человеком
def extract_audio_from_video(video_path, output_audio_path):
    print("Извлечение аудио из видео...")
    video = VideoFileClip(video_path)
    video.audio.write_audiofile(output_audio_path)
    return output_audio_path

# 2. Создание и сохранение модели голоса с использованием Wunjo AI
def create_voice_model(audio_path, voice_name, output_model_path):
    print(f"Создание модели голоса '{voice_name}'...")
    
    # Создаем директорию для сохранения модели, если она не существует
    os.makedirs(os.path.dirname(output_model_path), exist_ok=True)
    
    # Инициализация Wunjo TTS
    wunjo = WunjoTTS()
    
    # Обучение модели на аудио файле
    wunjo.train_voice_model(
        audio_path=audio_path,
        voice_name=voice_name,
        output_path=output_model_path
    )
    
    print(f"Модель голоса '{voice_name}' успешно создана и сохранена в '{output_model_path}'")
    return output_model_path

# 3. Озвучивание текста с использованием созданной модели
def synthesize_speech(text, model_path, output_path):
    print(f"Синтез речи с использованием модели из '{model_path}'...")
    
    # Инициализация Wunjo TTS
    wunjo = WunjoTTS()
    
    # Загрузка обученной модели
    wunjo.load_voice_model(model_path)
    
    # Генерация речи на русском языке
    wunjo.synthesize(
        text=text,
        language="ru",
        output_path=output_path
    )
    
    print(f"Синтез завершен. Результат сохранен в '{output_path}'")
    return output_path

def main():
    # Параметры
    video_path = "input_video.mp4"  # Путь к видео с человеком
    extracted_audio_path = "extracted_audio.wav"  # Путь для извлеченного аудио
    voice_name = "custom_voice"  # Название для модели голоса
    model_path = "models/custom_voice.pth"  # Путь для сохранения модели
    text_to_synthesize = "Привет, это тестовое сообщение, озвученное склонированным голосом на русском языке."  # Текст для озвучки
    output_speech_path = "synthesized_speech.wav"  # Путь для сохранения результата
    
    # 1. Извлечение аудио из видео
    extract_audio_from_video(video_path, extracted_audio_path)
    
    # 2. Создание модели голоса
    create_voice_model(extracted_audio_path, voice_name, model_path)
    
    # 3. Синтез речи с использованием созданной модели
    synthesize_speech(text_to_synthesize, model_path, output_speech_path)
    
    print(f"Готово! Синтезированная речь сохранена в '{output_speech_path}'")

if __name__ == "__main__":
    main()