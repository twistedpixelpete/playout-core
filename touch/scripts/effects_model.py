"""State-only allocator for independent audio playback voices."""

from dataclasses import dataclass


@dataclass
class Voice:
    index: int
    state: str = 'IDLE'
    clip_id: str = ''
    audio_bus: str = ''
    allocation_order: int = 0


class EffectsModel:
    def __init__(self, voice_count=4):
        self.voices = {
            index: Voice(index)
            for index in range(1, voice_count + 1)
        }
        self._allocation_order = 0

    def play(self, clip_id, audio_bus):
        idle = [
            voice for voice in self.voices.values()
            if voice.state == 'IDLE'
        ]
        if idle:
            voice = idle[0]
        else:
            voice = min(
                self.voices.values(),
                key=lambda item: item.allocation_order,
            )

        stolen_clip = voice.clip_id
        self._allocation_order += 1
        voice.state = 'PLAYING'
        voice.clip_id = clip_id
        voice.audio_bus = audio_bus
        voice.allocation_order = self._allocation_order
        return voice.index, stolen_clip

    def stop_clip(self, clip_id):
        stopped = []
        for voice in self.voices.values():
            if voice.state == 'PLAYING' and voice.clip_id == clip_id:
                stopped.append(voice.index)
                self.stop_voice(voice.index)
        return stopped

    def stop_voice(self, index):
        voice = self.voices[index]
        voice.state = 'IDLE'
        voice.clip_id = ''
        voice.audio_bus = ''

    def stop_all(self):
        stopped = [
            voice.index for voice in self.voices.values()
            if voice.state != 'IDLE'
        ]
        for index in stopped:
            self.stop_voice(index)
        return stopped
