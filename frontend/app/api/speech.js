import axios from 'axios';

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Only POST requests are allowed' });
  }

  const { text } = req.body;

  if (!text) {
    return res.status(400).json({ error: 'Text is required' });
  }

  try {
    const response = await axios.post(
      'https://api.openai.com/v1/audio/speech',
      {
        model: 'tts-1',
        voice: 'alloy', // Change this to any supported voice like 'alloy'
        input: text,
      },
      {
        headers: {
          'Authorization': `Bearer ${process.env.OPENAI_API_KEY}`, // Set your OpenAI API key here
          'Content-Type': 'application/json',
        },
        responseType: 'arraybuffer', // Set to arraybuffer to get audio data
      }
    );

    if (response.status === 200) {
      const audioBlob = new Blob([response.data], { type: 'audio/mp3' });
      const audioUrl = URL.createObjectURL(audioBlob);
      return res.status(200).json({ audioUrl });
    } else {
      return res.status(500).json({ error: 'Failed to fetch TTS audio' });
    }
  } catch (error) {
    console.error('Error in TTS API:', error);
    res.status(500).json({ error: 'Failed to fetch TTS audio' });
  }
}
