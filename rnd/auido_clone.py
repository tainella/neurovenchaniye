import os
import random
from tempfile import NamedTemporaryFile
from gtts import gTTS
from pydub import AudioSegment
from pydub.effects import speedup
from pydub.silence import detect_silence, split_on_silence
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip, AudioClip

def generate_continuous_funny_voice(text, output_path, speed_factor=1.5):
    """
    Генерирует смешной женский голос без пауз между предложениями
    
    Args:
        text: текст для озвучки
        output_path: путь для сохранения аудио файла
        speed_factor: множитель скорости (>1 - быстрее и выше, <1 - медленнее и ниже)
    
    Returns:
        Путь к созданному аудио файлу
    """
    try:
        # Создаем временный файл для полного текста
        temp_file = NamedTemporaryFile(delete=False, suffix='.mp3')
        temp_file.close()
        
        print("Генерация голоса...")
        # Генерируем голос для всего текста
        tts = gTTS(text=text, lang='ru', slow=False)
        tts.save(temp_file.name)
        
        # Загружаем аудио
        audio = AudioSegment.from_mp3(temp_file.name)
        
        print("Удаление всех пауз...")
        # Находим все участки тишины длиннее 150 мс
        silence_parts = detect_silence(audio, min_silence_len=150, silence_thresh=-40)
        
        # Создаем новое аудио без пауз
        continuous_audio = AudioSegment.empty()
        last_end = 0
        
        # Если нет пауз, используем оригинальное аудио
        if not silence_parts:
            continuous_audio = audio
        else:
            # Обрабатываем каждый участок тишины
            for start, end in silence_parts:
                # Добавляем аудио до тишины
                if start > last_end:
                    continuous_audio += audio[last_end:start]
                
                # Добавляем очень короткую паузу вместо длинной
                # (полностью удалять паузы нельзя, иначе слова будут сливаться)
                continuous_audio += AudioSegment.silent(duration=10)
                
                last_end = end
            
            # Добавляем оставшуюся часть аудио после последней паузы
            if last_end < len(audio):
                continuous_audio += audio[last_end:]
        
        print("Применение эффектов смешного голоса...")
        # Изменяем скорость (делает голос выше и быстрее)
        funny_sound = speedup(continuous_audio, speed_factor, 150)
        
        # Сохраняем измененный звук
        funny_sound.export(output_path, format="mp3")
        
        # Удаляем временный файл
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)
        
        return output_path
        
    except Exception as e:
        print(f"Ошибка при создании голоса: {e}")
        import traceback
        traceback.print_exc()
        # Удаляем временный файл в случае ошибки
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)
        return None

def replace_audio_with_voice_on_segments(video_path, text, num_segments=3, force_start_at_beginning=True):
    """
    Удаляет исходную аудиодорожку и накладывает смешной женский голос 
    на случайные отрывки видео, оставляя остальные отрывки без звука.
    Первый сегмент начинается с начала видео, если указано.
    
    Args:
        video_path: путь к видео файлу
        text: текст для озвучки
        num_segments: количество случайных отрывков для наложения голоса
        force_start_at_beginning: начинать первый сегмент с начала видео
    
    Returns:
        Путь к новому видео
    """
    try:
        # Загружаем видео без звука
        print(f"Загрузка видео (без звука): {video_path}")
        video = VideoFileClip(video_path).without_audio()
        
        # Получаем общую длительность видео
        video_duration = video.duration
        print(f"Длительность видео: {video_duration:.2f} секунд")
        
        # Создаем временный файл для голоса
        voice_file = NamedTemporaryFile(delete=False, suffix='.mp3')
        voice_file.close()
        
        # Генерируем непрерывный смешной женский голос без пауз
        generate_continuous_funny_voice(text, voice_file.name, speed_factor=1.5)
        
        # Загружаем аудио с голосом
        voice_audio = AudioFileClip(voice_file.name)
        voice_duration = voice_audio.duration
        print(f"Длительность голоса: {voice_duration:.2f} секунд")
        
        # Определяем длительность каждого сегмента
        segment_duration = voice_duration / num_segments
        
        # Генерируем сегменты
        segments = []
        
        # Если нужно начать с начала видео, добавляем первый сегмент принудительно
        if force_start_at_beginning:
            first_segment_duration = min(segment_duration, video_duration)
            segments.append((0, first_segment_duration))
            
            # Оставшаяся часть видео доступна для других сегментов
            available_ranges = [(first_segment_duration, video_duration)]
            remaining_segments = num_segments - 1
        else:
            available_ranges = [(0, video_duration)]
            remaining_segments = num_segments
        
        # Генерируем остальные случайные сегменты
        for i in range(remaining_segments):
            if not available_ranges:
                break
                
            # Выбираем случайный диапазон из доступных
            range_idx = random.randint(0, len(available_ranges) - 1)
            start_range, end_range = available_ranges[range_idx]
            
            # Проверяем, достаточно ли места для сегмента
            if end_range - start_range < segment_duration:
                # Если места недостаточно, используем весь доступный диапазон
                segment_start = start_range
                actual_duration = end_range - start_range
                available_ranges.pop(range_idx)
            else:
                # Выбираем случайное начало сегмента в пределах диапазона
                max_start = end_range - segment_duration
                segment_start = random.uniform(start_range, max_start)
                actual_duration = segment_duration
                
                # Обновляем доступные диапазоны
                available_ranges.pop(range_idx)
                if segment_start > start_range:
                    available_ranges.append((start_range, segment_start))
                if segment_start + actual_duration < end_range:
                    available_ranges.append((segment_start + actual_duration, end_range))
            
            segments.append((segment_start, actual_duration))
        
        # Сортируем сегменты по времени начала
        segments.sort(key=lambda x: x[0])
        
        # Создаем аудиоклипы для каждого сегмента и тишину для остальных частей
        audio_parts = []
        
        # Добавляем голос для каждого сегмента и тишину между ними
        for i, (segment_start, segment_duration) in enumerate(segments):
            # Если есть промежуток перед текущим сегментом, добавляем тишину
            if i == 0 and segment_start > 0:
                silence = AudioClip(lambda t: 0, duration=segment_start)
                audio_parts.append(silence)
            elif i > 0:
                prev_end = segments[i-1][0] + segments[i-1][1]
                if segment_start > prev_end:
                    silence_duration = segment_start - prev_end
                    silence = AudioClip(lambda t: 0, duration=silence_duration)
                    silence = silence.set_start(prev_end)
                    audio_parts.append(silence)
            
            # Вырезаем соответствующую часть голоса
            voice_start = i * (voice_duration / num_segments)
            voice_end = voice_start + segment_duration
            if voice_end > voice_duration:
                voice_end = voice_duration
                
            segment_voice = voice_audio.subclip(voice_start, voice_end)
            segment_voice = segment_voice.set_start(segment_start)
            audio_parts.append(segment_voice)
            
            print(f"Сегмент {i+1}: {segment_start:.2f}-{segment_start+segment_duration:.2f} сек, голос: {voice_start:.2f}-{voice_end:.2f} сек")
        
        # Если последний сегмент не заканчивается в конце видео, добавляем тишину
        if segments:
            last_end = segments[-1][0] + segments[-1][1]
            if last_end < video_duration:
                silence_duration = video_duration - last_end
                silence = AudioClip(lambda t: 0, duration=silence_duration)
                silence = silence.set_start(last_end)
                audio_parts.append(silence)
        
        # Если сегментов нет вообще, создаем полную тишину
        if not segments:
            silence = AudioClip(lambda t: 0, duration=video_duration)
            audio_parts.append(silence)
        
        # Создаем итоговую аудиодорожку
        final_audio = CompositeAudioClip(audio_parts)
        
        # Добавляем аудио к видео
        final_video = video.set_audio(final_audio)
        
        # Создаем имя для выходного файла
        output_path = os.path.splitext(video_path)[0] + "_continuous_voice.mp4"
        
        # Сохраняем результат
        print(f"Сохранение результата в {output_path}")
        final_video.write_videofile(output_path, codec='libx264', audio_codec='aac')
        
        # Закрываем все клипы
        video.close()
        voice_audio.close()
        final_audio.close()
        final_video.close()
        
        # Удаляем временный файл с голосом
        if os.path.exists(voice_file.name):
            os.unlink(voice_file.name)
        
        return output_path
        
    except Exception as e:
        print(f"Ошибка при обработке видео: {e}")
        import traceback
        traceback.print_exc()
        return None

# Пример использования
if __name__ == "__main__":
    # Путь к видео (замените на свой)
    video_path = "/Users/tainella/Documents/GIT/neurovenchaniye/data/popidka_2.mp4"
    
    # Текст для озвучки
    text = """Это длинный текст для смешного женского голоса. Он будет разбит на части и наложен на случайные отрывки видео. Представьте, что это очень забавный комментарий к происходящему на экране. Интересно, как это будет выглядеть в итоге? Давайте посмотрим результат. Возможно, получится очень смешно и необычно. Надеюсь, вам понравится."""
    
    # Удаляем исходную аудиодорожку и накладываем непрерывный голос без пауз
    # на случайные отрывки видео, начиная с самого начала видео
    output_video = replace_audio_with_voice_on_segments(
        video_path, 
        text, 
        num_segments=3, 
        force_start_at_beginning=True
    )
    
    print("Обработка завершена!")