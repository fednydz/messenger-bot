import express from 'express';
import axios from 'axios';
import dotenv from 'dotenv';

dotenv.config();

const app = express();
app.use(express.json());

const PAGE_ACCESS_TOKEN = process.env.PAGE_ACCESS_TOKEN;
const VERIFY_TOKEN = process.env.VERIFY_TOKEN;

// Webhook verification (GET)
app.get('/webhook', (req, res) => {
  const mode = req.query['hub.mode'];
  const token = req.query['hub.verify_token'];
  const challenge = req.query['hub.challenge'];

  if (mode === 'subscribe' && token === VERIFY_TOKEN) {
    console.log('Webhook verified!');
    res.status(200).send(challenge);
  } else {
    res.sendStatus(403);
  }
});

// Handle messages (POST)
app.post('/webhook', async (req, res) => {
  const body = req.body;

  if (body.object === 'page') {
    body.entry.forEach(entry => {
      entry.messaging.forEach(event => {
        if (event.message && event.message.text) {
          handleMessage(event.sender.id, event.message.text);
        }
      });
    });
    res.sendStatus(200);
  } else {
    res.sendStatus(404);
  }
});

// Send message function
async function handleMessage(senderId, text) {
  const reply = `أهلاً! لقد استلمت رسالتك: "${text}"\nأنا بوت تجريبي حالياً.`;
  
  try {
    await axios.post(
      'https://graph.facebook.com/v18.0/me/messages',
      {
        recipient: { id: senderId },
        message: { text: reply }
      },
      {
        params: { access_token: PAGE_ACCESS_TOKEN }
      }
    );
    console.log('Message sent!');
  } catch (error) {
    console.error('Error sending message:', error);
  }
}

export default app;
