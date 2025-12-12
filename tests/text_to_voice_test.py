from silero import silero_tts
model, example_text = silero_tts(language='ru',
                                 speaker='v5_ru')
audio = model.apply_tts(text=example_text)