// Session ID & Persona History Management
let currentPersona = 'general';
let currentSessionId = null;

const personaSessionMap = {
  general: null,
  weather: null,
  traffic: null,
  event: null
};

const personaHistoryMap = {
  general: '',
  weather: '',
  traffic: '',
  event: ''
};

const PERSONA_DESCRIPTIONS = {
  general: 'Persona: General Overview (Balanced analysis of crowds, weather, and activity)',
  weather: 'Persona: Weather & Atmosphere (Focused on cloud cover, rain, lighting, and temperature feel)',
  traffic: 'Persona: Traffic & Flow (Focused on vehicle congestion, pedestrian crosswalks, and movement)',
  event: 'Persona: Event & Sighting Spotter (Focused on billboards, costumes, performers, and crowds)'
};

const SUBAGENT_PROMPTS = {
  general: {
    agentName: 'general_agent',
    icon: '✨',
    title: 'General Overview Subagent',
    role: 'Specialized Persona Subagent',
    tools: 'get_latest_snapshot_tool, get_historical_snapshots_tool, get_earthcam_frame',
    prompt: `You are the General Overview AI Subagent for Times Square.
Your mission is to provide balanced, comprehensive urban insights by synthesizing crowd density, weather conditions, street traffic, and notable landmarks in Times Square.

Key Operating Rules:
1. For current status, check \`get_latest_snapshot_tool()\`. For historical queries over any time window (e.g., 2 hours, 24 hours, 7 days, or all history), call \`get_historical_snapshots_tool(minutes_back)\` with \`minutes_back\` matching the requested duration (e.g., 1440 for 24h, 10080 for 7d). NEVER claim you are limited to 1 hour!
2. For live real-time camera captures, call \`get_earthcam_frame()\`.
3. Provide a clear structured executive summary covering estimated crowd size, density classification, weather conditions, traffic movement, and notable sightings.
4. ALWAYS include the public image verification URL (\`image_url\`) in your output.`
  },
  weather: {
    agentName: 'weather_agent',
    icon: '🌤️',
    title: 'Weather & Atmosphere Subagent',
    role: 'Specialized Persona Subagent',
    tools: 'get_latest_snapshot_tool, get_historical_snapshots_tool, get_earthcam_frame',
    prompt: `You are the Weather & Atmosphere AI Subagent for Times Square.
Your mission is to analyze meteorological patterns, atmospheric visibility, ambient lighting, rain/snow conditions, and environmental comfort in Times Square.

Key Operating Rules:
1. Focus deeply on weather factors: cloud cover, atmospheric lighting (daylight, dusk, neon reflections, night), precipitation indicators, wet street surface reflections, and pedestrian thermal attire.
2. Support ANY requested historical timeframe (e.g., 2h, 24h, 7 days, or all time) using \`get_historical_snapshots_tool(minutes_back)\`. You can analyze weather progression across any duration requested!
3. Always include ambient atmospheric context alongside crowd numbers.
4. ALWAYS include the public image verification URL (\`image_url\`) in your output.`
  },
  traffic: {
    agentName: 'traffic_agent',
    icon: '🚕',
    title: 'Traffic & Mobility Subagent',
    role: 'Specialized Persona Subagent',
    tools: 'get_latest_snapshot_tool, get_historical_snapshots_tool, get_earthcam_frame',
    prompt: `You are the Traffic & Mobility AI Subagent for Times Square.
Your mission is to evaluate transportation dynamics, vehicle congestion, yellow cab density, bus/transit flow, crosswalk safety, and pedestrian throughput in Times Square.

Key Operating Rules:
1. Focus deeply on traffic activity: street vehicle density, gridlock indicators, crosswalk spillover, and traffic flow speed through major intersections (7th Ave, Broadway, 42nd-47th St).
2. Support ANY requested historical timeframe (e.g., 2h, 24h, 7 days, or all time) using \`get_historical_snapshots_tool(minutes_back)\`. You can analyze traffic congestion trends across any window requested!
3. Provide actionable transit and mobility insights for pedestrians and drivers.
4. ALWAYS include the public image verification URL (\`image_url\`) in your output.`
  },
  event: {
    agentName: 'event_agent',
    icon: '🎭',
    title: 'Event & Sighting Spotter Subagent',
    role: 'Specialized Persona Subagent',
    tools: 'get_latest_snapshot_tool, get_historical_snapshots_tool, get_earthcam_frame',
    prompt: `You are the Event & Sighting Spotter AI Subagent for Times Square.
Your mission is to spot notable landmarks, digital billboard advertisements, costumed characters, street performers, news crews, special staging, and large public gatherings in Times Square.

Key Operating Rules:
1. Focus deeply on visual sightings: commercial billboard campaigns, street performances, costumed characters, concert/broadcast stages, rallies, and unique visual highlights.
2. Support ANY requested historical timeframe (e.g., 2h, 24h, 7 days, or all time) using \`get_historical_snapshots_tool(minutes_back)\` to track how events or billboard activity evolved over time.
3. Provide vivid, engaging descriptions of notable sights and crowd interactions.
4. ALWAYS include the public image verification URL (\`image_url\`) in your output.`
  }
};

async function getOrCreateSessionForPersona(persona) {
  if (personaSessionMap[persona]) {
    currentSessionId = personaSessionMap[persona];
    const display = document.getElementById('session-id-display');
    if (display) display.textContent = currentSessionId;
    return currentSessionId;
  }

  try {
    const res = await fetch('/apps/app/users/web_user/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    if (res.ok) {
      const data = await res.json();
      personaSessionMap[persona] = data.id || data.name;
    } else {
      personaSessionMap[persona] = 'session_' + Math.random().toString(36).substring(2, 9);
    }
  } catch (e) {
    console.warn('Session creation fallback:', e);
    personaSessionMap[persona] = 'session_' + Math.random().toString(36).substring(2, 9);
  }

  currentSessionId = personaSessionMap[persona];
  const display = document.getElementById('session-id-display');
  if (display) display.textContent = currentSessionId;
  return currentSessionId;
}

function saveCurrentHistory() {
  const historyEl = document.getElementById('chat-history');
  if (historyEl && currentPersona) {
    personaHistoryMap[currentPersona] = historyEl.innerHTML;
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  initPersonas();
  initQuickPills();
  initForm();
  initIngestionTrigger();
  initPromptModal();
  fetchLatestMetrics();
  await getOrCreateSessionForPersona('general');
  saveCurrentHistory();
});

function initPromptModal() {
  const btnView = document.getElementById('btn-view-prompt');
  const btnClose = document.getElementById('btn-close-prompt-modal');
  const btnCopy = document.getElementById('btn-copy-prompt');
  const modal = document.getElementById('prompt-modal');

  if (btnView && modal) {
    btnView.addEventListener('click', () => {
      openPromptModal(currentPersona);
    });
  }

  if (btnClose && modal) {
    btnClose.addEventListener('click', () => {
      modal.style.display = 'none';
    });
  }

  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.style.display = 'none';
    });
  }

  if (btnCopy) {
    btnCopy.addEventListener('click', () => {
      const promptText = document.getElementById('modal-prompt-text').textContent;
      navigator.clipboard.writeText(promptText).then(() => {
        btnCopy.textContent = '✅ Copied!';
        setTimeout(() => { btnCopy.textContent = '📋 Copy Prompt'; }, 2000);
      });
    });
  }
}

function openPromptModal(personaKey) {
  const data = SUBAGENT_PROMPTS[personaKey] || SUBAGENT_PROMPTS.general;
  const modal = document.getElementById('prompt-modal');

  document.getElementById('modal-subagent-icon').textContent = data.icon;
  document.getElementById('modal-subagent-name').textContent = data.agentName;
  document.getElementById('modal-subagent-role').textContent = data.title;
  document.getElementById('modal-meta-agent').textContent = data.agentName;
  document.getElementById('modal-prompt-text').textContent = data.prompt;

  if (modal) modal.style.display = 'flex';
}


// Persona Card Selection
function initPersonas() {
  const cards = document.querySelectorAll('.persona-card');
  cards.forEach(card => {
    card.addEventListener('click', async () => {
      if (card.dataset.persona === currentPersona) return;

      // Save history for outgoing persona
      saveCurrentHistory();

      // UI Active Card Toggle
      cards.forEach(c => c.classList.remove('active'));
      card.classList.add('active');

      currentPersona = card.dataset.persona;
      document.getElementById('selected-persona-desc').textContent = PERSONA_DESCRIPTIONS[currentPersona] || '';

      // Get or restore persistent session ID for target persona
      await getOrCreateSessionForPersona(currentPersona);

      // Restore chat history for target persona
      const historyEl = document.getElementById('chat-history');
      if (personaHistoryMap[currentPersona]) {
        historyEl.innerHTML = personaHistoryMap[currentPersona];
      } else {
        historyEl.innerHTML = '';
        appendSystemMessage(`Switched to **${card.innerText.trim()}** persona.`);
        saveCurrentHistory();
      }
      historyEl.scrollTop = historyEl.scrollHeight;
    });
  });
}



// Quick Action Pills
function initQuickPills() {
  const pills = document.querySelectorAll('.pill');
  pills.forEach(pill => {
    pill.addEventListener('click', () => {
      document.getElementById('user-input').value = pill.dataset.prompt;
      sendMessage(pill.dataset.prompt);
    });
  });
}

// Form Handler
function initForm() {
  const form = document.getElementById('chat-form');
  const input = document.getElementById('user-input');
  
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (text) {
      sendMessage(text);
      input.value = '';
    }
  });
}

// Manual Ingestion Trigger
function initIngestionTrigger() {
  const btn = document.getElementById('btn-trigger-ingest');
  btn.addEventListener('click', async () => {
    btn.disabled = true;
    btn.textContent = '⏳ Ingesting frame...';
    try {
      const res = await fetch('/ingest', { method: 'POST' });
      const data = await res.json();
      if (data.status === 'success') {
        updateMetricsUI(data.snapshot);
      }
    } catch (err) {
      console.error('Ingestion error:', err);
    } finally {
      btn.disabled = false;
      btn.textContent = '🔄 Trigger Ingestion Now';
    }
  });
}

// Fetch Latest Snapshot Metrics (Fast GET endpoint for instant page load)
async function fetchLatestMetrics() {
  try {
    const res = await fetch('/latest_snapshot');
    const data = await res.json();
    if (data.status === 'success' && data.snapshot) {
      updateMetricsUI(data.snapshot);
      return;
    }
  } catch (e) {
    console.log('Fast snapshot load notice:', e);
  }

  // Fallback to trigger ingestion if no cached snapshot exists
  try {
    const res = await fetch('/ingest', { method: 'POST' });
    const data = await res.json();
    if (data.status === 'success' && data.snapshot) {
      updateMetricsUI(data.snapshot);
    }
  } catch (e) {
    console.log('Ingestion fallback load notice:', e);
  }
}

function updateMetricsUI(snapshot) {
  if (!snapshot) return;
  document.getElementById('metric-count').textContent = snapshot.estimated_people_count ?? '--';
  document.getElementById('metric-density').textContent = snapshot.crowd_density ?? '--';
  document.getElementById('metric-weather').textContent = snapshot.weather_summary ?? '--';
  
  if (snapshot.timestamp) {
    const timeStr = new Date(snapshot.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    document.getElementById('metric-time').textContent = timeStr;
  }

  const cameraGrid = document.getElementById('snapshot-grid');
  const placeholder = document.getElementById('image-placeholder');

  if (snapshot.camera_urls && Object.keys(snapshot.camera_urls).length > 0) {
    if (placeholder) placeholder.style.display = 'none';
    if (cameraGrid) cameraGrid.style.display = 'grid';

    const cams = ['tsnorth4k', 'tsrobo3', 'tsstreet', 'tsrobo1'];
    cams.forEach(cam => {
      const img = document.getElementById(`img-${cam}`);
      if (img) {
        if (snapshot.camera_urls && snapshot.camera_urls[cam]) {
          const url = snapshot.camera_urls[cam];
          img.src = url;
          img.style.display = 'block';
          img.onerror = () => { img.style.display = 'none'; };
          const cell = img.closest('.camera-cell');
          if (cell) {
            cell.onclick = () => window.open(url, '_blank');
          }
        } else {
          // If specific camera URL is missing, do not duplicate image_url from another camera
          img.style.display = 'none';
          img.removeAttribute('src');
        }
      }
    });
  }
}


// Append Messages
function appendUserMessage(text) {
  const history = document.getElementById('chat-history');
  const msg = document.createElement('div');
  msg.className = 'message user-msg';
  msg.innerHTML = `<div class="avatar">👤</div><div class="msg-content">${escapeHtml(text)}</div>`;
  history.appendChild(msg);
  history.scrollTop = history.scrollHeight;
  saveCurrentHistory();
}

function appendSystemMessage(markdownText) {
  const history = document.getElementById('chat-history');
  const msg = document.createElement('div');
  msg.className = 'message system-msg';
  msg.innerHTML = `<div class="avatar">🗽</div><div class="msg-content">${marked.parse(markdownText)}</div>`;
  history.appendChild(msg);
  history.scrollTop = history.scrollHeight;
  saveCurrentHistory();
}

// Send Message via /run_sse Streaming
async function sendMessage(userText) {
  appendUserMessage(userText);
  
  if (!currentSessionId) {
    await getOrCreateSessionForPersona(currentPersona);
  }

  // Format message with selected persona prefix instruction
  const personaPrefix = `[Persona Focus: ${currentPersona.toUpperCase()}] `;
  const fullText = personaPrefix + userText;


  // Create empty agent response bubble
  const history = document.getElementById('chat-history');
  const msg = document.createElement('div');
  msg.className = 'message agent-msg';
  
  const contentDiv = document.createElement('div');
  contentDiv.className = 'msg-content';
  contentDiv.innerHTML = '<span class="thought-badge">⚡ Agent connecting...</span><div class="text-body"></div>';
  
  msg.innerHTML = '<div class="avatar">🗽</div>';
  msg.appendChild(contentDiv);
  history.appendChild(msg);
  history.scrollTop = history.scrollHeight;

  const textBody = contentDiv.querySelector('.text-body');
  const thoughtBadge = contentDiv.querySelector('.thought-badge');
  let accumulatedMarkdown = '';

  try {
    const response = await fetch('/run_sse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        app_name: 'app',
        user_id: 'web_user',
        session_id: currentSessionId,
        new_message: {
          role: 'user',
          parts: [{ text: fullText }]
        },
        streaming: true
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); // Keep incomplete line in buffer

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const jsonStr = line.replace('data: ', '').trim();
          try {
            const event = JSON.parse(jsonStr);
            
            if (event.error) {
              accumulatedMarkdown += `\n\n⚠️ *Error processing request: ${event.error}*`;
              textBody.innerHTML = marked.parse(accumulatedMarkdown);
            }

            // Check for tool execution events or content events
            if (event.content && event.content.parts) {
              for (const part of event.content.parts) {
                if (part.text) {
                  const chunkText = part.text;
                  accumulatedMarkdown += chunkText;
                  textBody.innerHTML = marked.parse(accumulatedMarkdown);
                  
                  // Check if response contains image URL to update UI preview
                  const urlMatch = accumulatedMarkdown.match(/https:\/\/(storage\.googleapis\.com|i\.ibb\.co)\/[^\s\)]+/);
                  if (urlMatch) {
                    updateMetricsUI({ image_url: urlMatch[0] });
                  }
                }
              }
            } else if (event.text) {
              accumulatedMarkdown += event.text;
              textBody.innerHTML = marked.parse(accumulatedMarkdown);
            }

            if (event.type === 'thought' || event.thought) {
              thoughtBadge.textContent = '💭 ' + (event.thought || 'Analyzing camera data...');
            } else if (event.type === 'tool_call') {
              thoughtBadge.textContent = '🛠️ Executing tool: ' + (event.name || 'query_camera');
            } else {
              thoughtBadge.style.display = 'none';
            }

            history.scrollTop = history.scrollHeight;
          } catch (e) {
            // Non-json chunk
          }
        }
      }
    }

    if (!accumulatedMarkdown || accumulatedMarkdown.trim() === '') {
      accumulatedMarkdown = 'No response generated. Please check latest camera metrics or trigger a new camera ingestion.';
      textBody.innerHTML = marked.parse(accumulatedMarkdown);
    }
    saveCurrentHistory();
  } catch (err) {
    console.error('Streaming error:', err);
    thoughtBadge.style.display = 'none';
    textBody.innerHTML = `<span style="color: #ef4444;">Error connecting to agent stream: ${escapeHtml(err.message)}</span>`;
    saveCurrentHistory();
  }
}


function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
