import React, { useState } from 'react';
import axios from 'axios';
import { jwtDecode } from 'jwt-decode';
import GitGraph from './GitGraph';
import './App.css';

const API_BASE = 'http://localhost:8000';

// ─── Page constants ──────────────────────────────────────────────────
const PAGE_HOME = 'home';
const PAGE_ANALYSIS = 'analysis';
const PAGE_GIT = 'git';

function App() {
    const [token, setToken] = useState(() => {
        const stored = localStorage.getItem('token');
        if (!stored) return '';
        try {
            const { exp } = jwtDecode(stored);
            if (exp * 1000 < Date.now()) { localStorage.removeItem('token'); return ''; }
        } catch { localStorage.removeItem('token'); return ''; }
        return stored;
    });
    const [repoOwner, setRepoOwner] = useState('');
    const [repoName, setRepoName] = useState('');
    const [branch, setBranch] = useState('main');
    const [analysis, setAnalysis] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [aiFixes, setAiFixes] = useState({});
    const [aiLoading, setAiLoading] = useState({});
    const [prLoading, setPrLoading] = useState({});
    const [prResults, setPrResults] = useState({});
    const [page, setPage] = useState(PAGE_HOME);

    React.useEffect(() => {
        const urlParams = new URLSearchParams(window.location.search);
        const urlToken = urlParams.get('token');
        if (urlToken) {
            setToken(urlToken);
            localStorage.setItem('token', urlToken);
            window.history.replaceState({}, document.title, window.location.pathname);
        }
    }, []);

    const logout = () => {
        localStorage.removeItem('token');
        setToken('');
        setAnalysis(null);
        setPage(PAGE_HOME);
    };

    const goHome = () => setPage(PAGE_HOME);

    const analyzeRepo = async () => {
        setLoading(true);
        setError('');
        setAnalysis(null);
        try {
            const { data } = await axios.post(`${API_BASE}/analyze/full`, {
                owner: repoOwner,
                repo: repoName,
                branch: branch || 'main',
            }, { headers: { Authorization: `Bearer ${token}` } });
            setAnalysis(data);
            setPage(PAGE_ANALYSIS);          // navigate to analysis page
        } catch (err) {
            const detail = err.response?.data?.detail || err.message || 'Analysis failed.';
            setError(detail);
        }
        setLoading(false);
    };

    const requestAiFix = async (breakage, idx) => {
        setAiLoading(prev => ({ ...prev, [idx]: true }));
        try {
            const { data } = await axios.post(`${API_BASE}/ai/fix`, {
                breakage,
                code_snippet: `# Your usage of ${breakage.package}`,
            }, { headers: { Authorization: `Bearer ${token}` } });
            setAiFixes(prev => ({ ...prev, [idx]: data.suggested_fix }));
        } catch (err) {
            setAiFixes(prev => ({ ...prev, [idx]: '❌ AI fix failed: ' + (err.response?.data?.detail || err.message) }));
        }
        setAiLoading(prev => ({ ...prev, [idx]: false }));
    };

    const createPR = async (breakage, idx) => {
        setPrLoading(prev => ({ ...prev, [idx]: true }));
        setPrResults(prev => ({ ...prev, [idx]: null }));
        try {
            const affectedFiles = Object.keys(
                (analysis?.package_usage || {})[breakage.package] || {}
            );
            const { data } = await axios.post(`${API_BASE}/pr/create`, {
                owner: repoOwner,
                repo: repoName,
                breakage,
                code_snippet: `import ${breakage.package}`,
                affected_files: affectedFiles,
            }, { headers: { Authorization: `Bearer ${token}` } });
            setPrResults(prev => ({ ...prev, [idx]: { success: true, url: data.pr_url, number: data.pr_number } }));
        } catch (err) {
            const msg = err.response?.data?.detail || err.message || 'PR creation failed';
            setPrResults(prev => ({ ...prev, [idx]: { success: false, error: msg } }));
        }
        setPrLoading(prev => ({ ...prev, [idx]: false }));
    };

    const downloadReport = async () => {
        try {
            const response = await axios.post(
                `${API_BASE}/report/download/pdf`,
                { analysis },
                {
                    headers: { Authorization: `Bearer ${token}` },
                    responseType: 'blob',
                }
            );
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `parsec_${repoOwner}_${repoName}_report.pdf`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
        } catch (err) {
            console.error('PDF download failed:', err);
        }
    };

    // ── Login screen ─────────────────────────────────────────────────
    if (!token) {
        return (
            <div className="login-page">
                <h1>Parse<span>c</span></h1>
                <p>Analyse GitHub repository dependencies and detect breaking changes.</p>
                <button className="btn-login" onClick={() => window.location.href = `${API_BASE}/auth/github/login`}>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z" />
                    </svg>
                    Login with GitHub
                </button>
            </div>
        );
    }

    let decoded = null;
    try { decoded = jwtDecode(token); } catch { }

    // ── Shared navbar ─────────────────────────────────────────────────
    const Navbar = () => (
        <nav className="navbar">
            <div className="navbar-left">
                {page !== PAGE_HOME && (
                    <button className="btn-back" onClick={goHome}>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="15 18 9 12 15 6" />
                        </svg>
                        Back
                    </button>
                )}
                <div
                    className="navbar-brand"
                    style={{ cursor: page !== PAGE_HOME ? 'pointer' : 'default' }}
                    onClick={goHome}
                >
                    Parse<span>c</span>
                </div>
            </div>
            {decoded && (
                <div className="user-info">
                    <img src={decoded.avatar} alt="avatar" width="30" height="30" />
                    <span className="username">{decoded.username}</span>
                    <button className="btn-ghost" onClick={logout}>Logout</button>
                </div>
            )}
        </nav>
    );

    // ── HOME PAGE ─────────────────────────────────────────────────────
    if (page === PAGE_HOME) {
        return (
            <div className="app">
                <Navbar />
                <div className="main">
                    <div className="search-card">
                        <h2>Analyze a GitHub Repository</h2>
                        <div className="input-row">
                            <div className="input-group">
                                <label>Owner</label>
                                <input
                                    placeholder="e.g. tiangolo"
                                    value={repoOwner}
                                    onChange={e => setRepoOwner(e.target.value)}
                                />
                            </div>
                            <div className="input-group">
                                <label>Repository</label>
                                <input
                                    placeholder="e.g. fastapi"
                                    value={repoName}
                                    onChange={e => setRepoName(e.target.value)}
                                />
                            </div>
                            <div className="input-group" style={{ maxWidth: 140 }}>
                                <label>Branch</label>
                                <input
                                    placeholder="main"
                                    value={branch}
                                    onChange={e => setBranch(e.target.value)}
                                />
                            </div>
                        </div>

                        <div className="home-actions">
                            <button
                                className="btn-analyze"
                                onClick={analyzeRepo}
                                disabled={loading || !repoOwner || !repoName}
                            >
                                {loading ? <><span className="spinner" />Analyzing…</> : 'Analyze →'}
                            </button>
                            <button
                                className="btn-git"
                                onClick={() => setPage(PAGE_GIT)}
                                disabled={!repoOwner || !repoName}
                            >
                                ⎇ Git Graph →
                            </button>
                        </div>

                        {error && <p className="error-msg">❌ {error}</p>}
                    </div>
                </div>
            </div>
        );
    }

    // ── ANALYSIS PAGE ─────────────────────────────────────────────────
    if (page === PAGE_ANALYSIS && analysis) {
        return (
            <div className="app">
                <Navbar />
                <div className="main">
                    <div className="page-heading">
                        <h2>{analysis.repo.owner}/{analysis.repo.repo}</h2>
                        <span className="badge">{analysis.repo.branch}</span>
                        <button className="btn-download" onClick={downloadReport}>
                            📄 Download PDF
                        </button>
                    </div>

                    <div className="section">
                        <div className="section-header">
                            <h3>Dependencies</h3>
                            <span className="badge">{analysis.dependencies.length} found</span>
                        </div>
                        {analysis.dependencies.length === 0
                            ? <p className="empty">No dependency files detected.</p>
                            : <div className="deps-grid">
                                {analysis.dependencies.map((dep, i) => (
                                    <div key={i} className="dep-card">
                                        <strong>{dep.name}</strong>
                                        <span className="dep-ver">{dep.version_spec || 'unpinned'}</span>
                                        <span className="dep-file">{dep.file}</span>
                                    </div>
                                ))}
                            </div>
                        }
                    </div>

                    <hr className="divider" />

                    <div className="section">
                        <div className="section-header">
                            <h3>Breaking Changes</h3>
                            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                                <span className="badge">{analysis.breaking_changes.length} results</span>
                                <button
                                    className="btn-ai-fix"
                                    disabled={aiLoading['global']}
                                    onClick={() => requestAiFix({
                                        package: analysis.repo.repo,
                                        reason: `Summarise the dependency health of ${analysis.repo.owner}/${analysis.repo.repo} and suggest any upgrades.`,
                                    }, 'global')}
                                >
                                    {aiLoading['global'] ? <><span className="spinner" />Asking AI…</> : '✨ Ask AI'}
                                </button>
                            </div>
                        </div>
                        {analysis.breaking_changes.length === 0
                            ? <p className="empty">No breaking changes detected.</p>
                            : analysis.breaking_changes.map((b, i) => (
                                <div key={i} className={`breakage ${b.error ? 'error' : b.info ? 'info' : 'warn'}`}>
                                    <div className="breakage-main">
                                        <div className="breakage-text">
                                            {b.error
                                                ? <><span className="pkg">{b.package}</span><span className="detail"> — {b.error}</span></>
                                                : b.info
                                                    ? <><span className="pkg">{b.package}</span><span className="detail"> — {b.info}</span></>
                                                    : <><span className="pkg">{b.package}</span><span className="detail"> [{b.kind}] {b.location} — {b.reason}</span></>
                                            }
                                        </div>
                                        {!b.error && (
                                            <>
                                                <button
                                                    className="btn-ai-fix"
                                                    disabled={aiLoading[i]}
                                                    onClick={() => requestAiFix(b, i)}
                                                >
                                                    {aiLoading[i] ? <><span className="spinner" />Asking AI…</> : '✨ AI Fix'}
                                                </button>
                                                <button
                                                    className="btn-pr"
                                                    disabled={prLoading[i]}
                                                    onClick={() => createPR(b, i)}
                                                >
                                                    {prLoading[i] ? <><span className="spinner" />Creating…</> : '🔀 Create PR'}
                                                </button>
                                            </>
                                        )}
                                    </div>
                                    {aiFixes[i] && (
                                        <pre className="ai-fix-panel">{aiFixes[i]}</pre>
                                    )}
                                    {prResults[i] && (
                                        <div className={`pr-result ${prResults[i].success ? 'pr-success' : 'pr-error'}`}>
                                            {prResults[i].success
                                                ? <>✅ PR <a href={prResults[i].url} target="_blank" rel="noreferrer">#{prResults[i].number}</a> created successfully!</>
                                                : <>❌ PR failed: {prResults[i].error}</>
                                            }
                                        </div>
                                    )}
                                </div>
                            ))
                        }
                    </div>

                    <hr className="divider" />

                    {/* Quick link to git graph from analysis page */}
                    <div style={{ textAlign: 'center', paddingBottom: 24 }}>
                        <button className="btn-git" onClick={() => setPage(PAGE_GIT)}>
                            ⎇ View Git Graph →
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    // ── GIT GRAPH PAGE ───────────────────────────────────────────────
    if (page === PAGE_GIT) {
        return (
            <div className="app">
                <Navbar />
                <div className="main">
                    <div className="page-heading">
                        <h2>{repoOwner}/{repoName}</h2>
                        <span className="badge">Git Graph</span>
                    </div>
                    <GitGraph repoOwner={repoOwner} repoName={repoName} token={token} autoLoad />
                </div>
            </div>
        );
    }

    // Fallback
    return null;
}

export default App;
