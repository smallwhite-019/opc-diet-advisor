import React, { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { chat, loadSessions, loadHistory, removeSession, runSuggest, getGreeting,
  getProfile, getAccount, setNickname, clearAccount, exportAccount, login, register, getKb } from './api.js'

const CROWDS = [
  { key: '减脂塑形', icon: '🥗', label: '我想减脂' },
  { key: '增肌强化', icon: '💪', label: '我要增肌' },
  { key: '慢病调理', icon: '🩸', label: '血糖偏高' },
  { key: '控压调理', icon: '❤️', label: '血压偏高' },
]

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('opc_token') || '')
  const [username, setUsername] = useState(localStorage.getItem('opc_user') || '')
  if (!token) {
    return <LoginPage onAuth={(t, u) => { localStorage.setItem('opc_token', t); localStorage.setItem('opc_user', u); setToken(t); setUsername(u) }} />
  }
  return <ChatApp token={token} username={username} onLogout={() => { localStorage.removeItem('opc_token'); localStorage.removeItem('opc_user'); setToken(''); setUsername('') }} />

function LoginPage({ onAuth }) {
  const [mode, setMode] = useState('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [nickname, setNickname] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(e) {
    e.preventDefault(); setErr(''); setBusy(true)
    try {
      const fn = mode === 'login' ? login : register
      const res = mode === 'login' ? await fn(username, password) : await fn(username, password, nickname)
      if (res.ok) { onAuth(res.token, res.username) }
      else { setErr(res.detail || '操作失败') }
    } catch (e) { setErr('网络错误，请确认服务已启动') }
    finally { setBusy(false) }
  }
  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <div className="login-logo">🥗 AI 智能膳食顾问</div>
        <div className="login-sub">健康优选 · 登录后为您保存专属膳食档案</div>
        <div className="login-tabs">
          <button type="button" className={mode === 'login' ? 'on' : ''} onClick={() => { setMode('login'); setErr('') }}>登录</button>
          <button type="button" className={mode === 'register' ? 'on' : ''} onClick={() => { setMode('register'); setErr('') }}>注册</button>
        </div>
        <input placeholder="用户名（至少3位）" value={username} onChange={e => setUsername(e.target.value)} autoFocus />
        {mode === 'register' && <input placeholder="昵称（可选）" value={nickname} onChange={e => setNickname(e.target.value)} />}
        <input type="password" placeholder="密码（至少6位）" value={password} onChange={e => setPassword(e.target.value)} />
        {err && <div className="login-err">{err}</div>}
        <button className="login-btn" type="submit" disabled={busy}>{busy ? '处理中…' : (mode === 'login' ? '登录' : '注册并登录')}</button>
      </form>
    </div>
  )
}

function ChatApp({ token, username, onLogout }) {
  const [convId, setConvId] = useState('')
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sessions, setSessions] = useState([])
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarWidth, setSidebarWidth] = useState(260)

  function startResize(e) {
    e.preventDefault()
    const startX = e.clientX
    const startW = sidebarWidth
    function onMove(ev) {
      const next = Math.min(420, Math.max(180, startW + (ev.clientX - startX)))
      setSidebarWidth(next)
    }
    function onUp() {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }
  const [error, setError] = useState('')
  const [profile, setProfile] = useState(null)
  const [account, setAccount] = useState({ id: username, nickname: '' })
  const [showProfile, setShowProfile] = useState(false)
  const [showAccount, setShowAccount] = useState(false)
  const [showKb, setShowKb] = useState(false)
  const [kbData, setKbData] = useState(null)
  const [kbLoading, setKbLoading] = useState(false)
  const [expandedDocs, setExpandedDocs] = useState({})
  const [expandedChapters, setExpandedChapters] = useState({})
  const [activeBlock, setActiveBlock] = useState(null)
  const [nickEdit, setNickEdit] = useState('')
  const scrollRef = useRef(null)

  async function loadKb() {
    setKbLoading(true)
    try {
      const d = await getKb()
      setKbData(d)
    } catch (e) { setKbData(null) }
    finally { setKbLoading(false) }
  }
  function toggleDoc(name) { setExpandedDocs(p => ({ ...p, [name]: !p[name] })) }
  function toggleChapter(key) { setExpandedChapters(p => ({ ...p, [key]: !p[key] })) }

  useEffect(() => { refreshSessions() }, [])
  useEffect(() => { scrollRef.current && scrollRef.current.scrollIntoView() }, [messages])

  // 开场白：首次进入且无消息时，自动加载顾问问候（带引导+免责声明）
  useEffect(() => {
    if (messages.length === 0) {
      getGreeting().then(d => {
        setMessages([{ role: 'assistant', content: d.reply, model: d.model }])
      }).catch(() => {})
    }
  }, [])

  async function refreshSessions() {
    const d = await loadSessions(username); setSessions(d.sessions || [])
  }

  async function refreshProfile() {
    try { const d = await getProfile(username); setProfile(d.profile) } catch (e) {}
  }
  async function refreshAccount() {
    try { const d = await getAccount(username); setAccount({ id: d.id, nickname: d.nickname }); setNickEdit(d.nickname) } catch (e) {}
  }
  useEffect(() => { refreshProfile(); refreshAccount() }, [])

  async function send(text) {
    const msg = (text ?? input).trim()
    if (!msg) { setError('请输入您的问题'); return }
    if (msg.length > 500) { setError('输入内容过长，请精简后重试'); return }
    setError(''); setInput('')
    const userMsg = { role: 'user', content: msg }
    setMessages(m => [...m, userMsg])
    setLoading(true)
    try {
      const data = await chat(convId, msg)
      if (!convId && data.conv_id) { setConvId(data.conv_id); refreshSessions() }
      setMessages(m => [...m, { role: 'assistant', content: data.reply, sources: data.sources, model: data.model }])
      refreshProfile()
    } catch (e) {
      setMessages(m => [...m, { role: 'assistant', content: '服务繁忙，请稍后重试' }])
    } finally { setLoading(false) }
  }

  async function quick(crowd) {
    setError(''); setLoading(true)
    const userMsg = { role: 'user', content: CROWDS.find(c => c.key === crowd).label }
    setMessages(m => [...m, userMsg])
    try {
      const data = await runSuggest(crowd)
      if (!convId && data.conv_id) { setConvId(data.conv_id); refreshSessions() }
      setMessages(m => [...m, { role: 'assistant', content: data.reply, sources: data.sources, model: data.model }])
      refreshProfile()
    } catch (e) {
      setMessages(m => [...m, { role: 'assistant', content: '服务繁忙，请稍后重试' }])
    } finally { setLoading(false) }
  }

  async function openSession(id) {
    setConvId(id); setSidebarOpen(false)
    const d = await loadHistory(id, username)
    setMessages(d.messages || [])
  }

  async function newChat() {
    setConvId(''); setMessages([]); setSidebarOpen(false); setError('')
  }

  async function delSession(id) {
    await removeSession(id); if (id === convId) newChat(); refreshSessions()
  }

  return (
    <div className="app">
      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`} style={{ width: sidebarWidth, flex: '0 0 ' + sidebarWidth + 'px' }}>
        <div className="resizer" onMouseDown={startResize} title="拖动调整宽度" />
        <button className="newchat" onClick={newChat}>＋ 新建对话</button>
        <div className="side-actions">
          <button className="side-btn" onClick={() => { setShowAccount(false); setShowProfile(v => !v); refreshProfile() }}>📋 个人档案</button>
          <button className="side-btn" onClick={() => { setShowProfile(false); setShowAccount(v => !v); refreshAccount() }}>⚙️ 账号</button>
        </div>
        {showProfile && (
          <div className="panel">
            <div className="panel-title">个人膳食档案</div>
            {profile ? (
              <div className="profile">
                <div className="pf-row"><span className="pf-k">健康目标</span><span className="pf-v">{profile.health_goals.length ? profile.health_goals.join('、') : '暂无'}</span></div>
                <div className="pf-row"><span className="pf-k">饮食禁忌</span><span className="pf-v">{profile.dietary_taboos.length ? profile.dietary_taboos.join('、') : '暂无'}</span></div>
                <div className="pf-row"><span className="pf-k">关注话题</span><span className="pf-v">{profile.topics.length ? profile.topics.join('、') : '暂无'}</span></div>
                <div className="pf-row"><span className="pf-k">对话统计</span><span className="pf-v">{profile.conversation_count} 轮 / {profile.user_msg_count} 条咨询</span></div>
                {profile.last_active && <div className="pf-row"><span className="pf-k">最近活跃</span><span className="pf-v">{profile.last_active}</span></div>}
                <div className="pf-sum">{profile.summary}</div>
              </div>
            ) : <div className="pf-sum">加载中…</div>}
          </div>
        )}
        {showAccount && (
          <div className="panel">
            <div className="panel-title">账号后台</div>
            <div className="acct-id">账号ID：{account.id}</div>
            <div className="acct-edit">
              <input value={nickEdit} onChange={e => setNickEdit(e.target.value)} placeholder="设置昵称" maxLength={20} />
              <button onClick={async () => { await setNickname(username, nickEdit); refreshAccount() }}>保存</button>
            </div>
            <div className="acct-actions">
              <button onClick={async () => {
                const d = await exportAccount(username)
                const blob = new Blob([JSON.stringify(d, null, 2)], { type: 'application/json' })
                const a = document.createElement('a'); a.href = URL.createObjectURL(blob)
                a.download = 'diet-history.json'; a.click()
              }}>⬇ 导出对话</button>
              <button className="danger" onClick={async () => {
                if (confirm('确定清空全部对话历史？此操作不可恢复。')) {
                  await clearAccount(username); setMessages([]); setConvId(''); refreshSessions(); refreshProfile()
                }
              }}>🗑 清空历史</button>
            </div>
            <div className="acct-note">轻量本地账号：数据存于本地数据库，无密码，刷新或换设备（同账号ID）可恢复。</div>
          </div>
        )}
        <div className="sess-list">
          {sessions.map(s => (
            <div key={s.id} className={`sess ${s.id === convId ? 'active' : ''}`} onClick={() => openSession(s.id)}>
              <span>{s.title || '新对话'}</span>
              <button className="del" onClick={(e) => { e.stopPropagation(); delSession(s.id) }}>×</button>
            </div>
          ))}
        </div>
        <button className={`kb-toggle ${showKb ? 'on' : ''}`} onClick={() => { setShowKb(v => { if (!v && !kbData) loadKb(); return !v }) }}>
          📚 知识库{showKb ? '（收起）' : ''}
        </button>
        <div className="model-note">OPC 智能膳食顾问 · 健康优选</div>
      </aside>

      <main className="main">
        <header className="topbar">
          <button className="menu" onClick={() => setSidebarOpen(o => !o)}>☰</button>
          <span className="title">AI 智能膳食顾问</span>
          <span className="user-chip">{username}</span>
          <button className="logout-btn" onClick={onLogout} title="退出登录">退出</button>
        </header>

        {showKb ? (
          <section className="kb-view">
            <div className="kb-view-head">
              <h2>📚 知识库可视化</h2>
              <span className="kb-view-sub">共 {kbData ? kbData.total_blocks : '…'} 个知识块 · {kbData ? kbData.docs.length : '…'} 份素材 · 全部一次性展示</span>
              <button className="kb-close" onClick={() => setShowKb(false)}>返回对话 ✕</button>
            </div>
            {kbLoading && <div className="kb-placeholder">知识库加载中…</div>}
            {!kbLoading && !kbData && <div className="kb-placeholder">知识库加载失败，请重试。</div>}
            {!kbLoading && kbData && (
              <div className="kb-cards">
                {kbData.docs.flatMap(doc =>
                  doc.chapters.flatMap(ch =>
                    ch.sections.flatMap(sec =>
                      sec.blocks.map((b, bi) => (
                        <div key={doc.doc_name + ch.chapter + sec.section + bi} className="kb-card">
                          <div className="kb-card-meta">
                            <span className={`kb-card-badge kb-${doc.doc}`}>{doc.doc}</span>
                            <span className="kb-card-doc">《{doc.doc_name}》</span>
                            <span className="kb-card-sep">·</span>
                            <span className="kb-card-ch">{ch.chapter}</span>
                            {sec.section !== '（正文）' && <><span className="kb-card-sep">·</span><span className="kb-card-sec">{sec.section}</span></>}
                          </div>
                          <div className="kb-card-text">{b.text}</div>
                        </div>
                      ))
                    )
                  )
                )}
              </div>
            )}
          </section>
        ) : (
        <>
        <section className="quickbar">
          {CROWDS.map(c => (
            <button key={c.key} className="quick" onClick={() => quick(c.key)}>
              <span className="qicon">{c.icon}</span>{c.label}
            </button>
          ))}
        </section>

        <section className="messages">
          {messages.length === 0 && (
            <div className="welcome">
              <h2>👋 欢迎使用 AI 智能膳食顾问</h2>
              <p>告诉我您的健康目标（减脂 / 增肌 / 控糖 / 控压），或点击上方快捷入口，获取个性化膳食方案与营养解答。</p>
              <p className="warn">本建议仅供参考，不构成医疗建议，请咨询专业医师或注册营养师。</p>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              <div className="bubble">
                {m.role === 'assistant'
                  ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                  : m.content.split('\n').map((line, j) => <div key={j}>{line || ' '}</div>)}
                {m.sources && m.sources.length > 0 && (
                  <div className="sources">
                    来源：{m.sources.map(s => `《${s.doc}》${s.chapter}${s.section ? '·' + s.section : ''}`).join('；')}
                  </div>
                )}
                {m.model && <div className="model">由 {m.model} 生成 · 知识依据见来源标注</div>}
              </div>
            </div>
          ))}
          {loading && <div className="msg assistant"><div className="bubble loading">顾问正在思考…</div></div>}
          <div ref={scrollRef} />
        </section>
        </>
        )}

        {error && <div className="error-toast">{error}</div>}

        {!showKb && (
          <footer className="inputbar">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && send()}
              placeholder="请输入您的问题，例如：减脂期晚餐吃什么？"
            />
            <button onClick={() => send()}>发送</button>
          </footer>
        )}
      </main>
    </div>
  )
}
}
