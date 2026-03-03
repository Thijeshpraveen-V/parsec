import React, { useState } from 'react';
import axios from 'axios';

const API_BASE = 'http://localhost:8000';

export default function GitOperations({ owner, repo, token, branches = ['main'] }) {
    const [sourceBranch, setSourceBranch] = useState(branches[0] || 'main');
    const [targetBranch, setTargetBranch] = useState('');
    const [operation, setOperation] = useState('rebase');
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(false);

    const runOperation = async () => {
        setLoading(true);
        setResult(null);
        try {
            const { data } = await axios.post(
                `${API_BASE}/git/operation`,
                { owner, repo, source_branch: sourceBranch, target_branch: targetBranch, operation },
                { headers: { Authorization: `Bearer ${token}` } }
            );
            setResult(data);
        } catch (err) {
            setResult({ success: false, error: err.response?.data?.detail || err.message });
        }
        setLoading(false);
    };

    return (
        <div className="git-ops-panel">
            <h3>⚡ Git Operations</h3>
            <p className="git-ops-subtitle">
                Simulate rebase, merge, or cherry‑pick in an isolated clone — your repo is never modified.
            </p>

            <div className="op-controls">
                {/* Operation */}
                <div className="op-field">
                    <label>Operation</label>
                    <select value={operation} onChange={e => setOperation(e.target.value)}>
                        <option value="rebase">Rebase</option>
                        <option value="merge">Merge</option>
                        <option value="cherry-pick">Cherry‑pick</option>
                    </select>
                </div>

                {/* Source branch */}
                <div className="op-field">
                    <label>Source branch</label>
                    <select value={sourceBranch} onChange={e => setSourceBranch(e.target.value)}>
                        {branches.map(b => <option key={b} value={b}>{b}</option>)}
                    </select>
                </div>

                <div className="op-arrow">→</div>

                {/* Target branch */}
                <div className="op-field">
                    <label>Target branch</label>
                    <input
                        placeholder="e.g. feature/my-branch"
                        value={targetBranch}
                        onChange={e => setTargetBranch(e.target.value)}
                    />
                </div>

                <button
                    className="btn-run-op"
                    onClick={runOperation}
                    disabled={loading || !targetBranch}
                >
                    {loading ? <><span className="spinner" />Running…</> : `Run ${operation}`}
                </button>
            </div>

            {result && (
                <div className={`op-result ${result.success ? 'op-success' : 'op-error'}`}>
                    {/* Status header */}
                    <div className="op-result-header">
                        <span>{result.success ? '✅ Success' : '❌ Failed'}</span>
                        {result.conflicts && (
                            <span className="op-conflict-badge">⚠️ Conflicts detected</span>
                        )}
                    </div>

                    {/* Error message */}
                    {result.error && <pre className="op-pre op-pre-error">{result.error}</pre>}

                    {/* Before / After logs */}
                    {(result.before_log || result.after_log) && (
                        <div className="op-log-grid">
                            <div>
                                <p className="op-log-label">Before</p>
                                <pre className="op-pre">{result.before_log || '—'}</pre>
                            </div>
                            <div>
                                <p className="op-log-label">After</p>
                                <pre className="op-pre">{result.after_log || '—'}</pre>
                            </div>
                        </div>
                    )}

                    {/* Diff stat */}
                    {result.diff_stat && (
                        <>
                            <p className="op-log-label">Diff summary</p>
                            <pre className="op-pre">{result.diff_stat}</pre>
                        </>
                    )}

                    {/* Raw output */}
                    {result.output && (
                        <>
                            <p className="op-log-label">Output</p>
                            <pre className="op-pre">{result.output}</pre>
                        </>
                    )}
                </div>
            )}
        </div>
    );
}
