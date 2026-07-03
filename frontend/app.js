/* KithFun MVP client.
 * Two API backends behind one interface:
 *  - RemoteApi: talks to the FastAPI server (same origin, or KITHFUN_CONFIG.apiUrl)
 *  - DemoApi:  fully client-side game state in localStorage — used on GitHub Pages
 *              (no backend), or with ?demo=1
 */
(() => {
  "use strict";

  const cfg = window.KITHFUN_CONFIG || {};
  const params = new URLSearchParams(location.search);
  const IS_DEMO =
    params.has("demo") ||
    cfg.forceDemo === true ||
    (location.hostname.endsWith("github.io") && !cfg.apiUrl);
  const API_BASE = cfg.apiUrl || "";

  const $ = (id) => document.getElementById(id);
  const DAY = () => {
    // EAT (UTC+3) calendar day, matching the server
    const d = new Date(Date.now() + 3 * 3600 * 1000);
    return d.toISOString().slice(0, 10);
  };
  const prevDay = (key) => {
    const d = new Date(key + "T00:00:00Z");
    d.setUTCDate(d.getUTCDate() - 1);
    return d.toISOString().slice(0, 10);
  };

  function haversineM(lat1, lng1, lat2, lng2) {
    const R = 6371000, rad = Math.PI / 180;
    const dphi = (lat2 - lat1) * rad, dl = (lng2 - lng1) * rad;
    const a = Math.sin(dphi / 2) ** 2 +
      Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dl / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(a));
  }

  /* ---------------- Remote API ---------------- */

  class RemoteApi {
    constructor() { this.token = localStorage.getItem("kf_token") || null; }
    get authed() { return !!this.token; }

    async _req(path, opts = {}) {
      const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
      if (this.token) headers["Authorization"] = `Bearer ${this.token}`;
      const res = await fetch(API_BASE + path, { ...opts, headers });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || `Request failed (${res.status})`);
      return body;
    }

    async register(username, password) {
      const { token } = await this._req("/api/auth/register", {
        method: "POST", body: JSON.stringify({ username, password }),
      });
      this.token = token; localStorage.setItem("kf_token", token);
    }
    async login(username, password) {
      const { token } = await this._req("/api/auth/login", {
        method: "POST", body: JSON.stringify({ username, password }),
      });
      this.token = token; localStorage.setItem("kf_token", token);
    }
    logout() { this.token = null; localStorage.removeItem("kf_token"); }

    me() { return this._req("/api/me"); }
    quests() { return this._req("/api/quests"); }
    leaderboard() { return this._req("/api/leaderboard"); }
    mapConfig() { return this._req("/api/map/config"); }
    checkin(questId, lat, lng) {
      return this._req(`/api/quests/${questId}/checkin`, {
        method: "POST", body: JSON.stringify({ lat, lng }),
      });
    }

    duals() { return this._req("/api/duals"); }
    dualSuggestions() { return this._req("/api/duals/suggestions"); }
    challenge(username) {
      return this._req("/api/duals/challenge", { method: "POST", body: JSON.stringify({ username }) });
    }
    acceptDual(id) { return this._req(`/api/duals/${id}/accept`, { method: "POST" }); }
    declineDual(id) { return this._req(`/api/duals/${id}/decline`, { method: "POST" }); }

    connectLive(onUpdate) {
      try {
        const base = API_BASE || location.origin;
        const wsUrl = base.replace(/^http/, "ws") + "/ws/leaderboard";
        const ws = new WebSocket(wsUrl);
        ws.onmessage = (ev) => {
          const msg = JSON.parse(ev.data);
          if (msg.type === "leaderboard") onUpdate(msg);
        };
        const ping = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send("ping");
        }, 25000);
        ws.onclose = () => { clearInterval(ping); setTimeout(() => this.connectLive(onUpdate), 5000); };
      } catch { /* polling fallback still runs */ }
    }
  }

  /* ---------------- Demo API ---------------- */

  const DEMO_FACTIONS = [
    { id: 1, name: "House Simba", emblem: "🦁", color: "#f5a623", points: 1240 },
    { id: 2, name: "House Chui", emblem: "🐆", color: "#00e5a0", points: 1105 },
    { id: 3, name: "House Ndovu", emblem: "🐘", color: "#4a9eff", points: 980 },
    { id: 4, name: "House Kifaru", emblem: "🦏", color: "#e0508c", points: 1310 },
  ];
  const DEMO_RIVALS = [
    { username: "mwangi_dev", points: 480, streak: 6, f: 0 },
    { username: "akinyi.designs", points: 455, streak: 9, f: 3 },
    { username: "brian_quant", points: 390, streak: 4, f: 1 },
    { username: "wanjiru_k", points: 310, streak: 3, f: 2 },
    { username: "otis254", points: 240, streak: 2, f: 3 },
  ];
  const DEMO_QUEST_DEFS = [
    ["Library Grind", "Hit the books where the silence lives.", "📚", 50, 75],
    ["Lecture Legend", "Show up. Half of success is attendance.", "🎓", 40, 75],
    ["Cafeteria Social", "Break bread, make allies.", "🍛", 30, 60],
    ["Lab Rat", "Where the real experiments happen.", "🧪", 60, 75],
    ["Field Day", "Touch grass. Literally.", "⚽", 40, 100],
    ["Innovation Hub", "Ship something. Anything.", "💡", 70, 60],
  ];
  const DEMO_CENTER = { lat: -1.2795, lng: 36.8163, name: "Demo Campus (University of Nairobi)" };

  class DemoApi {
    constructor() {
      const raw = localStorage.getItem("kf_demo");
      this.state = raw ? JSON.parse(raw) : null;
    }
    get authed() { return !!this.state; }
    _save() { localStorage.setItem("kf_demo", JSON.stringify(this.state)); }

    async register(username) {
      const faction = DEMO_FACTIONS[Math.floor(Math.random() * DEMO_FACTIONS.length)];
      this.state = {
        username, factionId: faction.id, points: 0, streak: 0,
        lastDay: null, completed: {}, center: DEMO_CENTER,
      };
      this._save();
    }
    async login(username) { return this.register(username); }
    logout() { this.state = null; localStorage.removeItem("kf_demo"); }

    recenter(lat, lng) {
      this.state.center = { lat, lng, name: "Your Campus" };
      this._save();
    }

    _faction() { return DEMO_FACTIONS.find((f) => f.id === this.state.factionId); }
    _todayCompleted() { return this.state.completed[DAY()] || []; }

    async me() {
      const f = this._faction();
      return {
        username: this.state.username, points: this.state.points, streak: this.state.streak,
        faction: { ...f, points: f.points + this._factionBonus(f.id) },
        completed_today: this._todayCompleted(),
      };
    }

    async quests() {
      const { lat, lng } = this.state.center;
      const offsets = [
        [0.0012, 0.0008], [-0.0010, 0.0014], [0.0006, -0.0013],
        [-0.0015, -0.0006], [0.0020, -0.0002], [-0.0004, 0.0021],
      ];
      return DEMO_QUEST_DEFS.map(([title, description, icon, points, radius_m], i) => ({
        id: i + 1, title, description, icon, points, radius_m,
        lat: lat + offsets[i][0], lng: lng + offsets[i][1],
      }));
    }

    _factionBonus(fid) { return fid === this.state.factionId ? this.state.points : 0; }

    async checkin(questId, lat, lng) {
      const quest = (await this.quests()).find((q) => q.id === questId);
      const dist = haversineM(lat, lng, quest.lat, quest.lng);
      if (dist > quest.radius_m)
        throw new Error(`Too far away — you are ~${Math.round(dist)}m out, get within ${quest.radius_m}m.`);
      const day = DAY();
      const done = this.state.completed[day] || [];
      if (done.includes(questId)) throw new Error("Already completed today — come back tomorrow.");

      if (this.state.lastDay !== day) {
        this.state.streak = this.state.lastDay === prevDay(day) ? this.state.streak + 1 : 1;
        this.state.lastDay = day;
      }
      done.push(questId);
      this.state.completed = { [day]: done };
      this.state.points += quest.points;
      this._save();
      this._dualsOnCheckin(questId);
      const f = this._faction();
      return {
        ok: true, points_awarded: quest.points, total_points: this.state.points,
        streak: this.state.streak, faction_points: f.points + this._factionBonus(f.id),
        message: `+${quest.points} pts for ${f.name}!`,
      };
    }

    async leaderboard() {
      const me = this.state
        ? [{
            username: this.state.username + " (you)", points: this.state.points,
            streak: this.state.streak, faction_name: this._faction().name,
            faction_emblem: this._faction().emblem,
          }]
        : [];
      const players = [...DEMO_RIVALS.map((r) => ({
        username: r.username, points: r.points, streak: r.streak,
        faction_name: DEMO_FACTIONS[r.f].name, faction_emblem: DEMO_FACTIONS[r.f].emblem,
      })), ...me].sort((a, b) => b.points - a.points);
      return {
        factions: DEMO_FACTIONS
          .map((f) => ({ ...f, points: f.points + (this.state ? this._factionBonus(f.id) : 0) }))
          .sort((a, b) => b.points - a.points),
        players,
      };
    }

    async mapConfig() {
      const c = this.state?.center || DEMO_CENTER;
      return { campus_name: c.name, lat: c.lat, lng: c.lng, zoom: 16 };
    }
    connectLive() { /* no live socket in demo */ }

    /* --- demo duals: a scripted rival keeps the feature alive single-player --- */

    _duals() { return this.state.duals || []; }
    _notifyDuals() { if (this.onDualsChanged) this.onDualsChanged(); }

    async maybeSpawnIncomingChallenge() {
      if (!this.state || this._duals().length) return;
      const quest = (await this.quests())[2];
      setTimeout(() => {
        if (!this.state || this._duals().length) return;
        this.state.duals = [{
          id: 1, status: "pending", incoming: true, partner: "akinyi.designs",
          quest: { id: quest.id, title: quest.title, icon: quest.icon, lat: quest.lat, lng: quest.lng },
          bonus_points: 100, expires_epoch: null, you_done: false, partner_done: false,
        }];
        this._save();
        this._notifyDuals();
      }, 8000);
    }

    async duals() { return [...this._duals()].sort((a, b) => b.id - a.id); }

    async dualSuggestions() {
      const open = new Set(this._duals().filter((d) => ["pending", "active"].includes(d.status)).map((d) => d.partner));
      return DEMO_RIVALS.filter((r) => !open.has(r.username)).slice(0, 4)
        .map((r) => ({ username: r.username, faction_emblem: DEMO_FACTIONS[r.f].emblem }));
    }

    async challenge(username) {
      const rival = DEMO_RIVALS.find((r) => r.username === username);
      if (!rival) throw new Error("No player with that username.");
      if (this._duals().some((d) => d.partner === username && ["pending", "active"].includes(d.status)))
        throw new Error("You already have an open Dual Quest with this player.");
      const quests = await this.quests();
      const notDone = quests.filter((q) => !this._todayCompleted().includes(q.id));
      if (!notDone.length) throw new Error("You two have completed every quest today — challenge again tomorrow.");
      const quest = notDone[Math.floor(Math.random() * notDone.length)];
      const dual = {
        id: Date.now() % 1000000, status: "pending", incoming: false, partner: username,
        quest: { id: quest.id, title: quest.title, icon: quest.icon, lat: quest.lat, lng: quest.lng },
        bonus_points: 100, expires_epoch: null, you_done: false, partner_done: false,
      };
      this.state.duals = [...this._duals(), dual];
      this._save();
      setTimeout(() => {  // rival accepts a few seconds later
        const d = this._duals().find((x) => x.id === dual.id);
        if (d && d.status === "pending") {
          d.status = "active";
          d.expires_epoch = Math.floor(Date.now() / 1000) + 2 * 3600;
          this._save();
          this._notifyDuals();
        }
      }, 5000);
      return dual;
    }

    async acceptDual(id) {
      const d = this._duals().find((x) => x.id === id);
      if (!d || d.status !== "pending") throw new Error("This challenge is no longer pending.");
      d.status = "active";
      d.expires_epoch = Math.floor(Date.now() / 1000) + 2 * 3600;
      this._save();
      return d;
    }

    async declineDual(id) {
      const d = this._duals().find((x) => x.id === id);
      if (!d || d.status !== "pending") throw new Error("This challenge is no longer pending.");
      d.status = "declined";
      this._save();
      return d;
    }

    _dualsOnCheckin(questId) {
      for (const d of this._duals()) {
        if (d.status !== "active" || d.quest.id !== questId) continue;
        d.you_done = true;
        this._save();
        setTimeout(() => {  // rival hustles over and completes their side
          if (d.status !== "active") return;
          d.partner_done = true;
          d.status = "completed";
          this.state.points += d.bonus_points;
          this._save();
          this._notifyDuals();
          if (this.onDualCompleted) this.onDualCompleted(d);
        }, 6000);
      }
    }
  }

  /* ---------------- App ---------------- */

  const api = IS_DEMO ? new DemoApi() : new RemoteApi();
  let map, meMarker, myPos = null, questMarkers = {}, questCircles = {}, questsCache = [];
  let registering = true;

  function toast(msg, isError = false) {
    const el = $("toast");
    el.textContent = msg;
    el.classList.toggle("error", isError);
    el.classList.remove("hidden");
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.add("hidden"), 3200);
  }

  function setMyPos(lat, lng, pan = false) {
    myPos = { lat, lng };
    if (!meMarker) {
      meMarker = L.marker([lat, lng], {
        icon: L.divIcon({ className: "", html: '<div class="me-marker"></div>', iconSize: [18, 18], iconAnchor: [9, 9] }),
        zIndexOffset: 1000,
      }).addTo(map);
    } else {
      meMarker.setLatLng([lat, lng]);
    }
    if (pan) map.panTo([lat, lng]);
    renderQuests(questsCache);
  }

  function locate(pan = true) {
    if (!navigator.geolocation) return toast("Geolocation not supported on this device", true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setMyPos(pos.coords.latitude, pos.coords.longitude, pan);
        if (IS_DEMO && api.authed) {
          api.recenter(pos.coords.latitude, pos.coords.longitude);
          refreshQuests().then(() => toast("Quests moved to your area 🎯"));
        }
      },
      () => toast("Couldn't get your location — check permissions", true),
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }

  async function refreshQuests() {
    questsCache = await api.quests();
    const me = await api.me();
    renderQuests(questsCache, me.completed_today);
    return questsCache;
  }

  function renderQuests(quests, completedToday) {
    if (!quests.length) return;
    if (completedToday === undefined) completedToday = renderQuests._lastDone || [];
    renderQuests._lastDone = completedToday;

    const list = $("quest-list");
    list.innerHTML = "";
    for (const q of quests) {
      const done = completedToday.includes(q.id);
      const dist = myPos ? haversineM(myPos.lat, myPos.lng, q.lat, q.lng) : null;
      const near = dist !== null && dist <= q.radius_m;

      // marker
      const icon = L.divIcon({
        className: "", iconSize: [34, 34], iconAnchor: [17, 17],
        html: `<div class="quest-marker ${done ? "done" : ""}">${q.icon}</div>`,
      });
      if (questMarkers[q.id]) {
        questMarkers[q.id].setIcon(icon).setLatLng([q.lat, q.lng]);
        questCircles[q.id].setLatLng([q.lat, q.lng]);
      } else {
        questMarkers[q.id] = L.marker([q.lat, q.lng], { icon }).addTo(map)
          .bindPopup(`<b>${q.icon} ${q.title}</b><br>${q.description}<br><b style="color:#f5a623">+${q.points} pts</b>`);
        questCircles[q.id] = L.circle([q.lat, q.lng], {
          radius: q.radius_m, color: "#00e5a0", weight: 1, opacity: 0.5, fillOpacity: 0.07,
        }).addTo(map);
      }

      // list item
      const li = document.createElement("li");
      li.className = "quest-item" + (done ? " done" : "");
      li.innerHTML = `
        <div class="quest-icon">${q.icon}</div>
        <div class="quest-info">
          <div class="quest-title">${q.title} <span class="quest-pts">+${q.points}</span></div>
          <div class="quest-desc">${q.description}</div>
          <div class="quest-meta">${
            done ? "✅ done today"
              : dist === null ? "enable location to play"
              : near ? '<span class="near">📍 in range!</span>'
              : `${Math.round(dist)}m away`
          }</div>
        </div>
        <button class="btn-checkin" data-q="${q.id}" ${done || !near ? "disabled" : ""}>
          ${done ? "DONE" : "CHECK IN"}
        </button>`;
      li.querySelector(".quest-icon").style.cursor = "pointer";
      li.querySelector(".quest-icon").onclick = () => map.setView([q.lat, q.lng], 17);
      list.appendChild(li);
    }

    list.querySelectorAll(".btn-checkin:not([disabled])").forEach((btn) => {
      btn.onclick = () => doCheckin(parseInt(btn.dataset.q, 10));
    });
  }

  async function doCheckin(questId) {
    if (!myPos) return toast("Enable location first 🎯", true);
    try {
      const res = await api.checkin(questId, myPos.lat, myPos.lng);
      toast(`🔥 ${res.message} Streak: ${res.streak}`);
      await Promise.all([refreshHud(), refreshQuests(), refreshLeaderboard(), refreshDuals()]);
    } catch (e) {
      toast(e.message, true);
    }
  }

  async function refreshHud() {
    const me = await api.me();
    $("hud-points").textContent = me.points;
    $("hud-streak").textContent = me.streak;
    $("hud-faction").textContent = `${me.faction.emblem} ${me.faction.name}`;
    $("hud-faction").style.color = me.faction.color;
  }

  function renderLeaderboard(data) {
    const maxPts = Math.max(...data.factions.map((f) => f.points), 1);
    $("faction-board").innerHTML = data.factions.map((f) => `
      <div class="faction-row">
        <span class="faction-emblem">${f.emblem}</span>
        <span class="faction-name" style="color:${f.color}">${f.name}</span>
        <div class="faction-bar-track">
          <div class="faction-bar" style="width:${(f.points / maxPts) * 100}%;background:${f.color}"></div>
        </div>
        <span class="faction-pts">${f.points}</span>
      </div>`).join("");
    $("player-board").innerHTML = data.players.map((p) => `
      <li class="player-row">
        <span>${p.faction_emblem}</span>
        <span class="player-name">${p.username}</span>
        <span class="player-streak">🔥${p.streak}</span>
        <span class="player-pts">${p.points}</span>
      </li>`).join("");
  }

  async function refreshLeaderboard() {
    renderLeaderboard(await api.leaderboard());
  }

  /* ---------------- Dual Quests ---------------- */

  function timeLeft(expiresEpoch) {
    const s = expiresEpoch - Math.floor(Date.now() / 1000);
    if (s <= 0) return "expired";
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
    return h > 0 ? `${h}h ${m}m left` : `${m}m left`;
  }

  function renderDuals(duals) {
    const pendingIncoming = duals.filter((d) => d.status === "pending" && d.incoming).length;
    const badge = $("allies-badge");
    badge.textContent = pendingIncoming || "";
    badge.classList.toggle("hidden", pendingIncoming === 0);

    const list = $("dual-list");
    list.innerHTML = "";
    for (const d of duals) {
      const li = document.createElement("li");
      li.className = "dual-card" +
        (d.status === "active" ? " active-dual" : "") +
        (["expired", "declined"].includes(d.status) ? " muted" : "");

      let head, sub, actions = "";
      if (d.status === "pending" && d.incoming) {
        head = `⚔️ <b>${d.partner}</b> challenged you!`;
        sub = `${d.quest.icon} ${d.quest.title} · accept to start the 2h clock · +${d.bonus_points} each`;
        actions = `<div class="dual-actions">
          <button class="btn-accept" data-act="accept" data-id="${d.id}">ACCEPT</button>
          <button class="btn-decline" data-act="decline" data-id="${d.id}">DECLINE</button></div>`;
      } else if (d.status === "pending") {
        head = `📨 Challenge sent to <b>${d.partner}</b>`;
        sub = `${d.quest.icon} ${d.quest.title} · waiting for them to accept…`;
      } else if (d.status === "active") {
        head = `🎯 ${d.quest.icon} ${d.quest.title} <span class="spacer"></span>⏳ ${timeLeft(d.expires_epoch)}`;
        sub = `with <b>${d.partner}</b> · you ${d.you_done ? '<span class="ok">✓</span>' : '<span class="wait">…</span>'} · them ${d.partner_done ? '<span class="ok">✓</span>' : '<span class="wait">…</span>'} · +${d.bonus_points} each`;
      } else if (d.status === "completed") {
        head = `🤝 Allies with <b>${d.partner}</b>`;
        sub = `${d.quest.icon} ${d.quest.title} · +${d.bonus_points} pts each`;
      } else {
        head = d.status === "declined" ? `🚫 ${d.partner} — declined` : `⌛ ${d.partner} — expired`;
        sub = `${d.quest.icon} ${d.quest.title}`;
      }

      li.innerHTML = `<div class="dual-head">${head}</div><div class="dual-sub">${sub}</div>${actions}`;
      if (d.status === "active") {
        li.style.cursor = "pointer";
        li.addEventListener("click", (e) => {
          if (!e.target.closest("button")) map.setView([d.quest.lat, d.quest.lng], 17);
        });
      }
      list.appendChild(li);
    }

    list.querySelectorAll("button[data-act]").forEach((btn) => {
      btn.onclick = async () => {
        try {
          const id = parseInt(btn.dataset.id, 10);
          if (btn.dataset.act === "accept") {
            await api.acceptDual(id);
            toast("⚔️ Dual Quest ON — 2 hours, go go go!");
          } else {
            await api.declineDual(id);
          }
          await refreshDuals();
        } catch (e) { toast(e.message, true); }
      };
    });
  }

  async function refreshDuals() {
    if (!api.authed) return;
    try {
      renderDuals(await api.duals());
      const sugg = await api.dualSuggestions();
      $("suggestions").innerHTML = sugg.map((s) =>
        `<button class="suggestion-chip" data-u="${s.username}">${s.faction_emblem} ${s.username}</button>`
      ).join("");
      $("suggestions").querySelectorAll(".suggestion-chip").forEach((chip) => {
        chip.onclick = () => { $("challenge-input").value = chip.dataset.u; sendChallenge(); };
      });
    } catch { /* transient — poll will retry */ }
  }

  async function sendChallenge() {
    const username = $("challenge-input").value.trim();
    if (!username) return;
    try {
      await api.challenge(username);
      $("challenge-input").value = "";
      toast(`📨 Challenge sent to ${username}!`);
      await refreshDuals();
    } catch (e) { toast(e.message, true); }
  }

  /* ---------------- Auth flow ---------------- */

  function showAuth() {
    $("auth-modal").classList.remove("hidden");
    $("auth-password").classList.toggle("hidden", IS_DEMO);
    $("btn-auth-toggle").classList.toggle("hidden", IS_DEMO);
    $("modal-sub") && null;
  }

  async function submitAuth() {
    const username = $("auth-username").value.trim();
    const password = $("auth-password").value;
    const err = $("auth-error");
    err.classList.add("hidden");
    if (username.length < 3) {
      err.textContent = "Username: 3+ characters (letters, numbers, _)";
      return err.classList.remove("hidden");
    }
    if (!IS_DEMO && password.length < 6) {
      err.textContent = "Password: 6+ characters";
      return err.classList.remove("hidden");
    }
    try {
      if (registering) await api.register(username, password);
      else await api.login(username, password);
      $("auth-modal").classList.add("hidden");
      await enterGame();
      toast(IS_DEMO ? "Welcome to the DEMO — tap the map to move around 🕹️" : `Welcome, ${username} ⚡`);
    } catch (e) {
      err.textContent = e.message;
      err.classList.remove("hidden");
    }
  }

  /* ---------------- Boot ---------------- */

  async function enterGame() {
    await refreshHud();
    const conf = await api.mapConfig();
    map.setView([conf.lat, conf.lng], conf.zoom);
    if (!myPos) setMyPos(conf.lat, conf.lng);  // start avatar at campus center until located
    await refreshQuests();
    await refreshLeaderboard();
    await refreshDuals();
    api.connectLive(renderLeaderboard);
    if (IS_DEMO) {
      api.onDualsChanged = async () => {
        await refreshDuals();
        const incoming = (await api.duals()).find((d) => d.status === "pending" && d.incoming);
        if (incoming) toast(`⚔️ ${incoming.partner} challenged you to a Dual Quest!`);
      };
      api.onDualCompleted = async (d) => {
        toast(`🤝 Dual Quest complete with ${d.partner}! +${d.bonus_points} pts`);
        await Promise.all([refreshHud(), refreshDuals()]);
      };
      api.maybeSpawnIncomingChallenge();
    } else {
      navigator.geolocation?.watchPosition(
        (pos) => setMyPos(pos.coords.latitude, pos.coords.longitude),
        () => {}, { enableHighAccuracy: true }
      );
    }
    setInterval(() => { refreshHud(); refreshLeaderboard(); refreshDuals(); }, 30000);  // polling fallback
  }

  function initMap() {
    map = L.map("map", { zoomControl: false, attributionControl: true })
      .setView([DEMO_CENTER.lat, DEMO_CENTER.lng], 16);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
      maxZoom: 19,
    }).addTo(map);
    if (IS_DEMO) {
      // demo superpower: tap the map to teleport (so desktop visitors can play)
      map.on("click", (e) => setMyPos(e.latlng.lat, e.latlng.lng));
    }
  }

  function initUi() {
    if (IS_DEMO) $("demo-badge").classList.remove("hidden");

    $("btn-locate").onclick = () => locate(true);
    $("btn-auth-submit").onclick = submitAuth;
    $("auth-password").addEventListener("keydown", (e) => e.key === "Enter" && submitAuth());
    $("auth-username").addEventListener("keydown", (e) => e.key === "Enter" && (IS_DEMO ? submitAuth() : $("auth-password").focus()));
    $("btn-auth-toggle").onclick = () => {
      registering = !registering;
      $("btn-auth-submit").textContent = registering ? "Enter" : "Log in";
      $("btn-auth-toggle").textContent = registering ? "I already have an account" : "Create a new account";
    };

    document.querySelectorAll(".tab").forEach((tab) => {
      tab.onclick = () => {
        document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
        tab.classList.add("active");
        for (const name of ["quests", "allies", "leaderboard"]) {
          $(`panel-${name}`).classList.toggle("hidden", tab.dataset.tab !== name);
        }
        if (tab.dataset.tab === "allies") refreshDuals();
      };
    });

    $("btn-challenge").onclick = sendChallenge;
    $("challenge-input").addEventListener("keydown", (e) => e.key === "Enter" && sendChallenge());

    $("sheet-handle").onclick = () => $("sheet").classList.toggle("expanded");
  }

  async function boot() {
    initMap();
    initUi();
    if ("serviceWorker" in navigator && location.protocol === "https:") {
      navigator.serviceWorker.register("sw.js").catch(() => {});
    }
    if (api.authed) {
      try { await enterGame(); return; }
      catch { api.logout(); }
    }
    await refreshLeaderboard().catch(() => {});
    showAuth();
  }

  boot();
})();
