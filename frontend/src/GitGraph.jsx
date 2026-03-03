import React, { useState, useEffect } from 'react';
import axios from 'axios';
import GitOperations from './GitOperations';

const API_BASE = 'http://localhost:8000';

// ─── Branch colour palette ────────────────────────────────────────────
const BRANCH_COLORS = [
    '#388bfd', '#3fb950', '#f78166', '#d2a8ff',
    '#ffa657', '#79c0ff', '#56d364', '#ff7b72',
];
const colorFor = (name, branches) => {
    const idx = branches.indexOf(name);
    return BRANCH_COLORS[(idx < 0 ? 0 : idx) % BRANCH_COLORS.length];
};

// ─── SVG git graph renderer ───────────────────────────────────────────
function CommitGraph({ commits, branches }) {
    const ROW_H = 48;
    const COL_W = 20;
    const R = 6;
    const svgH = Math.max(commits.length * ROW_H + 20, 60);
    const svgW = Math.max(branches.length * COL_W + 40, 120);

    // Assign each commit a "lane" based on detected branches
    const laneMap = {};
    branches.forEach((b, i) => { laneMap[b] = i; });

    return (
        <svg width={svgW} height={svgH} style={{ display: 'block', flexShrink: 0 }}>
            {commits.map((c, i) => {
                const lane = c.branches.length > 0
                    ? (laneMap[c.branches[0]] ?? 0)
                    : 0;
                const cx = 16 + lane * COL_W;
                const cy = 24 + i * ROW_H;
                const color = c.branches.length > 0 ? colorFor(c.branches[0], branches) : '#8b949e';

                return (
                    <g key={i}>
                        {/* Vertical line down */}
                        {i < commits.length - 1 && (
                            <line
                                x1={cx} y1={cy + R}
                                x2={cx} y2={cy + ROW_H - R}
                                stroke={color} strokeWidth={2} strokeOpacity={0.5}
                            />
                        )}
                        {/* Commit dot */}
                        <circle cx={cx} cy={cy} r={R} fill={color} />
                        {c.branches.map((b, bi) => (
                            <rect key={bi}
                                x={cx + 10 + bi * 64} y={cy - 9}
                                width={Math.min(b.length * 7, 62)} height={18}
                                rx={9} fill={colorFor(b, branches)} fillOpacity={0.18}
                            />
                        ))}
                    </g>
                );
            })}
        </svg>
    );
}

// ─── Main component ───────────────────────────────────────────────────
export default function GitGraph({ repoOwner, repoName, token, autoLoad = false }) {
    const [gitData, setGitData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const fetchGraph = async () => {
        if (!repoOwner || !repoName) return;
        setLoading(true);
        setError('');
        setGitData(null);
        try {
            const { data } = await axios.post(
                `${API_BASE}/git/visualize`,
                { owner: repoOwner, repo: repoName, branch: 'main' },
                { headers: { Authorization: `Bearer ${token}` } }
            );
            setGitData(data);
        } catch (err) {
            setError(err.response?.data?.detail || err.message || 'Failed to fetch git graph');
        }
        setLoading(false);
    };

    // Auto-fetch when opened directly from the Git Graph page button
    useEffect(() => {
        if (autoLoad) fetchGraph();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return (
        <div className="git-graph-panel">
            <div className="git-graph-header">
                <div>
                    <h3>Git Commit Graph</h3>
                    {gitData && (
                        <span className="git-repo-label">
                            {gitData.repo} — {gitData.branches.length} branch{gitData.branches.length !== 1 ? 'es' : ''},&nbsp;
                            {gitData.commits.length} commits
                        </span>
                    )}
                </div>
                <button
                    className="btn-analyze"
                    onClick={fetchGraph}
                    disabled={loading || !repoOwner || !repoName}
                >
                    {loading ? <><span className="spinner" />Loading…</> : 'Load Graph'}
                </button>
            </div>

            {error && <p className="error-msg">❌ {error}</p>}

            {!gitData && !loading && !error && (
                <p className="empty">Enter a repo above and click "Load Graph" to visualize commits.</p>
            )}

            {gitData && (
                <div className="git-graph-body">
                    {/* Branch legend */}
                    <div className="git-branch-legend">
                        {gitData.branches.map((b, i) => (
                            <span key={i} className="branch-pill" style={{
                                borderColor: BRANCH_COLORS[i % BRANCH_COLORS.length],
                                color: BRANCH_COLORS[i % BRANCH_COLORS.length],
                            }}>
                                ⎇ {b}
                            </span>
                        ))}
                    </div>

                    {/* Commits table */}
                    <div className="git-commits-area">
                        <CommitGraph commits={gitData.commits} branches={gitData.branches} />
                        <div className="git-commit-list">
                            {gitData.commits.map((c, i) => (
                                <div key={i} className="git-commit-row">
                                    <code className="commit-hash">{c.hash || '───'}</code>
                                    <span className="commit-msg">{c.message || '(branch marker)'}</span>
                                    {c.branches.map((b, bi) => (
                                        <span key={bi} className="branch-tag" style={{
                                            background: `${BRANCH_COLORS[(gitData.branches.indexOf(b)) % BRANCH_COLORS.length]}22`,
                                            color: BRANCH_COLORS[(gitData.branches.indexOf(b)) % BRANCH_COLORS.length],
                                        }}>{b}</span>
                                    ))}
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Raw log */}
                    {gitData.log_sample?.length > 0 && (
                        <details className="git-raw-log">
                            <summary>Raw git log</summary>
                            <pre>{gitData.log_sample.join('\n')}</pre>
                        </details>
                    )}

                    {/* Git operations — uses live branches from graph */}
                    <GitOperations
                        owner={repoOwner}
                        repo={repoName}
                        token={token}
                        branches={gitData.branches}
                    />
                </div>
            )}
        </div>
    );
}
