const express = require('express');
const path = require('path');
const os = require('os');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// In-memory Database
let polls = [
  {
    id: 'poll-1',
    title: '是否同意 115 學年度社課時間調整為每週三晚上 7:00 至 9:00？',
    description: '因考量幹部與社員課程安排，提議調整社課時間。',
    options: ['同意', '不同意', '無意見'],
    status: 'draft', // 'draft' | 'open' | 'closed'
    votes: [0, 0, 0],
    votedTokens: []
  }
];

let activePollId = 'poll-1';
const ADMIN_TOKEN = 'ndhu-tkd-admin-secret-token-8888';

// Helper to get local IP address
function getLocalIpAddress() {
  const interfaces = os.networkInterfaces();
  for (const name of Object.keys(interfaces)) {
    for (const iface of interfaces[name]) {
      // Skip internal (loopback) and non-IPv4 addresses
      if (iface.family === 'IPv4' && !iface.internal) {
        return iface.address;
      }
    }
  }
  return 'localhost';
}

// Middleware to check Admin Authentication
function adminAuth(req, res, next) {
  const authHeader = req.headers['authorization'];
  if (authHeader === `Bearer ${ADMIN_TOKEN}`) {
    next();
  } else {
    res.status(401).json({ error: 'Unauthorized: Admin access required.' });
  }
}

// --- Public APIs ---

// Login API
app.post('/api/auth/login', (req, res) => {
  const { username, password } = req.body;
  if (username === 'user' && password === 'user1234') {
    res.json({ success: true, token: ADMIN_TOKEN });
  } else {
    res.status(401).json({ success: false, error: '帳號或密碼錯誤！' });
  }
});

// Get currently active poll (safe for voters - no vote counts revealed)
app.get('/api/poll/active', (req, res) => {
  const clientToken = req.query.token;
  const activePoll = polls.find(p => p.id === activePollId);

  if (!activePoll) {
    return res.json({ poll: null });
  }

  const hasVoted = clientToken ? activePoll.votedTokens.includes(clientToken) : false;

  res.json({
    poll: {
      id: activePoll.id,
      title: activePoll.title,
      description: activePoll.description,
      options: activePoll.options,
      status: activePoll.status,
      hasVoted: hasVoted
    }
  });
});

// Cast an anonymous vote
app.post('/api/poll/vote', (req, res) => {
  const { pollId, optionIndex, token } = req.body;

  if (!token) {
    return res.status(400).json({ error: '遺失選民辨識碼！' });
  }

  const poll = polls.find(p => p.id === pollId);
  if (!poll) {
    return res.status(404).json({ error: '找不到該投票主題！' });
  }

  if (poll.status !== 'open') {
    return res.status(400).json({ error: '投票目前未開放或已結束！' });
  }

  if (poll.votedTokens.includes(token)) {
    return res.status(400).json({ error: '您在此投票中已經投過票囉！' });
  }

  const index = parseInt(optionIndex, 10);
  if (isNaN(index) || index < 0 || index >= poll.options.length) {
    return res.status(400).json({ error: '無效的選項！' });
  }

  // Record vote anonymously (just increment count)
  poll.votes[index]++;
  // Track that this token has voted to prevent double voting
  poll.votedTokens.push(token);

  res.json({ success: true, message: '投票成功，感謝您的參與！' });
});


// --- Admin APIs (Protected) ---

// Get all polls
app.get('/api/admin/polls', adminAuth, (req, res) => {
  res.json({ polls, activePollId });
});

// Create a new poll
app.post('/api/admin/polls', adminAuth, (req, res) => {
  const { title, description, options } = req.body;
  if (!title || !options || options.length < 2) {
    return res.status(400).json({ error: '標題與至少兩個選項為必填！' });
  }

  const newPoll = {
    id: 'poll-' + Date.now(),
    title,
    description: description || '',
    options: options.filter(o => o.trim() !== ''),
    status: 'draft',
    votes: new Array(options.length).fill(0),
    votedTokens: []
  };

  polls.push(newPoll);
  res.status(201).json(newPoll);
});

// Set active poll
app.put('/api/admin/polls/:id/active', adminAuth, (req, res) => {
  const { id } = req.params;
  const poll = polls.find(p => p.id === id);
  if (!poll) {
    return res.status(404).json({ error: '找不到該投票主題！' });
  }
  activePollId = id;
  res.json({ success: true, activePollId });
});

// Update poll status (open / closed / draft)
app.put('/api/admin/polls/:id/status', adminAuth, (req, res) => {
  const { id } = req.params;
  const { status } = req.body; // 'open' | 'closed' | 'draft'

  if (!['open', 'closed', 'draft'].includes(status)) {
    return res.status(400).json({ error: '無效的投票狀態！' });
  }

  const poll = polls.find(p => p.id === id);
  if (!poll) {
    return res.status(404).json({ error: '找不到該投票主題！' });
  }

  // If opening, we can clear votes/tokens if it was previously closed to allow a fresh start,
  // or we can keep them. Let's provide a clean slate if going from 'draft' to 'open', or let the admin reset explicitly.
  poll.status = status;
  res.json({ success: true, poll });
});

// Reset poll votes
app.post('/api/admin/polls/:id/reset', adminAuth, (req, res) => {
  const { id } = req.params;
  const poll = polls.find(p => p.id === id);
  if (!poll) {
    return res.status(404).json({ error: '找不到該投票主題！' });
  }

  poll.votes = new Array(poll.options.length).fill(0);
  poll.votedTokens = [];
  res.json({ success: true, poll });
});

// Delete poll
app.delete('/api/admin/polls/:id', adminAuth, (req, res) => {
  const { id } = req.params;
  const pollIndex = polls.findIndex(p => p.id === id);
  if (pollIndex === -1) {
    return res.status(404).json({ error: '找不到該投票主題！' });
  }

  polls.splice(pollIndex, 1);
  if (activePollId === id) {
    activePollId = polls.length > 0 ? polls[0].id : null;
  }
  res.json({ success: true, activePollId });
});

// Get results of active poll (reveals counts)
app.get('/api/admin/results', adminAuth, (req, res) => {
  const activePoll = polls.find(p => p.id === activePollId);
  if (!activePoll) {
    return res.status(404).json({ error: '目前無啟用中的投票！' });
  }
  res.json({
    title: activePoll.title,
    options: activePoll.options,
    votes: activePoll.votes,
    totalVotes: activePoll.votedTokens.length
  });
});

// Get Server IP for QR code and connections
app.get('/api/server-info', (req, res) => {
  const ip = getLocalIpAddress();
  res.json({ ip, port: PORT });
});

// Catch-all for spa
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`====================================================`);
  console.log(`東華跆拳社匿名投票系統啟動成功！`);
  console.log(`本機存取網址: http://localhost:${PORT}`);
  console.log(`局域網存取網址: http://${getLocalIpAddress()}:${PORT}`);
  console.log(`====================================================`);
});
