import torch
from diffusers import HunyuanVideoAvatarPipeline
from diffusers.utils import export_to_video
import librosa  # для аудио, если нужно
from PIL import Image

# Загружаем пайплайн (требует GPU)
pipe = HunyuanVideoAvatarPipeline.from_pretrained(
    "tencent/HunyuanVideo-Avatar",
    torch_dtype=torch.float16
)
pipe.enable_model_cpu_offload()  # Оптимизация для меньшего VRAM

# Пример: изображение аватара (замени на свой путь)
avatar_image = Image.open("path/to/your_avatar.jpg").resize((512, 512))

# Пример: аудио-файл с озвучкой промпта (сгенерируй TTS заранее, напр. из GPT)
audio_path = "path/to/prompt_audio.wav"  # Аудио длиной 2-5 сек

# Генерация видео (эмоция: "happy", разрешение 512x512, 25 кадров/сек, 50 шагов)
video_frames = pipe(
    image=avatar_image,
    audio=audio_path,
    num_inference_steps=50,
    height=512,
    width=512,
    num_frames=25,  # ~1 сек видео
    guidance_scale=7.5,
    emotion="happy"  # Опции: neutral, happy, sad и т.д.
).frames[0]

# Сохраняем видео
video_path = "output_avatar_video.mp4"
export_to_video(video_frames, video_path, fps=25)

print(f"Видео с аватаром сохранено: {video_path}")