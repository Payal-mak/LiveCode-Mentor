import * as vscode from 'vscode';
import axios from 'axios';
import { SidebarProvider } from './SidebarProvider';

const BACKEND_URL = 'http://localhost:8000';
let debounceTimer: ReturnType<typeof setTimeout>;
let sidebarProvider: SidebarProvider;
let lastMistake: { type: string; description: string } | null = null;
let currentMode: string = 'learning'; // FR17: track mode


// GAMIFICATION: Track copy-paste
let lastCodeLength = 0;
let consecutiveTypedChars = 0;

// Copy-paste detection
vscode.workspace.onDidChangeTextDocument((event) => {
    if (event.document.uri.scheme !== 'file') { return; }

    const newLength = event.document.getText().length;
    const change = event.contentChanges[0];

    if (change && change.text.length > 0) {
        const addedLength = change.text.length;

        // Copy-paste = large chunk added at once (50+ chars)
        if (addedLength >= 50 && !change.text.includes('\n\n')) {
            consecutiveTypedChars = 0;
            // Penalize copy-paste
            axios.post(`${BACKEND_URL}/score`, {
                delta: -5,
                reason: "copy-paste detected"
            }).then(res => {
                sidebarProvider.sendMessage('scorePenalty', {
                    message: `📋 Try typing this yourself! -5 pts`,
                    score: res.data.score
                });
            }).catch(() => {});

        } else {
            // Normal typing
            consecutiveTypedChars += addedLength;

            // Reward 50 consecutive typed chars
            if (consecutiveTypedChars >= 50) {
                consecutiveTypedChars = 0;
                axios.post(`${BACKEND_URL}/score`, {
                    delta: +3,
                    reason: "typed 50+ chars without copy-paste"
                }).then(res => {
                    sidebarProvider.sendMessage('scoreReward', {
                        message: `✍️ Great typing! +3 pts`,
                        score: res.data.score,
                        new_badges: res.data.new_badges || []
                    });
                    // Award pure-coder badge
                    if (res.data.new_badges && res.data.new_badges.length > 0) {
                        sidebarProvider.sendMessage('newBadge', res.data.new_badges[0]);
                    }
                }).catch(() => {});
            }
        }
    }

    lastCodeLength = newLength;
});

export function activate(context: vscode.ExtensionContext) {
    console.log('LiveCode Mentor is now active!');

    sidebarProvider = new SidebarProvider(context.extensionUri);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider('livecodeMentor', sidebarProvider)
    );

    // Generate flow command
    context.subscriptions.push(
        vscode.commands.registerCommand('livecode-mentor.generateFlow', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showWarningMessage('Open a code file first!');
                return;
            }
            const code = editor.document.getText();
            const language = editor.document.languageId;

            if (code.trim().length === 0) {
                vscode.window.showWarningMessage('File is empty!');
                return;
            }

            console.log('[LiveCode Mentor] Generating flow diagram...');
            try {
                const res = await axios.post(`${BACKEND_URL}/flow`, {
                    code, language, trigger: 'flow'
                });
                sidebarProvider.sendMessage('flow', res.data.mermaid);
            } catch (e) {
                console.error('[LiveCode Mentor] Flow error:', e);
                sidebarProvider.sendMessage('flow', '');
            }
        })
    );
    context.subscriptions.push(
        vscode.commands.registerCommand('livecode-mentor.reanalyze', () => {
            const editor = vscode.window.activeTextEditor;
            if (editor) { sendCodeToBackend(editor.document, 'change'); }
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('livecode-mentor.generateTrace', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) { return; }
            try {
                const res = await axios.post(`${BACKEND_URL}/trace`, {
                    code: editor.document.getText(),
                    language: editor.document.languageId
                });
                sidebarProvider.sendMessage('trace', res.data);
            } catch (e) {
                console.error('[LiveCode Mentor] Trace error:', e);
            }
        })
    );

    // FR11: Check fix command
    context.subscriptions.push(
        vscode.commands.registerCommand('livecode-mentor.checkFix', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) { return; }
            try {
                const res = await axios.post(`${BACKEND_URL}/check-fix`, {
                    code: editor.document.getText(),
                    language: editor.document.languageId
                });
                if (res.data.fixed) {
                    lastMistake = null;
                    sidebarProvider.sendMessage('hint', { has_mistake: false });
                    sidebarProvider.sendMessage('scoreReward', {
                        message: `🐛 Bug fixed! +10 pts`,
                        score: res.data.new_score,
                        new_badges: res.data.new_badges || []
                    });
                    if (res.data.new_badges && res.data.new_badges.length > 0) {
                        sidebarProvider.sendMessage('newBadge', res.data.new_badges[0]);
                    }
                    vscode.window.showInformationMessage('Great job! Issue resolved! 🎉');
                } else {
                    vscode.window.showWarningMessage('Not quite — check the hint again!');
                }
            } catch (e) {
                console.error('[LiveCode Mentor] Check fix error:', e);
            }
        })
    );

    // FR19: Explain This Line — right-click context menu command
    context.subscriptions.push(
        vscode.commands.registerCommand('livecode-mentor.explainLine', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showWarningMessage('Open a code file first!');
                return;
            }

            // Fix: use active cursor line, not selection
            const lineIndex = editor.selection.active.line;
            const lineContent = editor.document.lineAt(lineIndex).text;

            // Skip empty lines and comment-only lines
            if (!lineContent.trim() || lineContent.trim().startsWith('#') || lineContent.trim().startsWith('//')) {
                vscode.window.showInformationMessage('Place cursor on a code line (not a comment).');
                return;
            }

            // Always show loading immediately so user knows it's working
            sidebarProvider.sendMessage('lineExplainLoading', {
                line: lineContent.trim(),
                lineNumber: lineIndex + 1
            });

            // Switch to explain tab automatically
            sidebarProvider.sendMessage('switchTab', 'explanation');

            try {
                const res = await axios.post(`${BACKEND_URL}/explain-line`, {
                    line: lineContent.trim(),
                    line_number: lineIndex + 1,
                    language: editor.document.languageId,
                    code: editor.document.getText()
                });
                sidebarProvider.sendMessage('lineExplain', res.data);
            } catch (e) {
                console.error('[LiveCode Mentor] Explain line error:', e);
                sidebarProvider.sendMessage('lineExplain', {
                    explanation: 'Could not explain this line. Make sure the backend is running.'
                });
            }
        })
    );

    // FR23: Get current code mistakes for progress tab
    context.subscriptions.push(
        vscode.commands.registerCommand('livecode-mentor.getCurrentMistakes', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) { return; }
            try {
                const res = await axios.post(`${BACKEND_URL}/current-mistakes`, {
                    code: editor.document.getText(),
                    language: editor.document.languageId
                });
                sidebarProvider.sendMessage('currentMistakes', res.data);
            } catch (e) {
                console.error('[LiveCode Mentor] Current mistakes error:', e);
            }
        })
    );

    // Health check
    axios.get(`${BACKEND_URL}/health`)
    .then(res => {
        vscode.window.showInformationMessage(`LiveCode Mentor: ${res.data.status}`);
        // Fetch initial score
        return axios.get(`${BACKEND_URL}/score`);
    })
    .then(res => {
        sidebarProvider.sendMessage('scoreInit', {
            score: res.data.score,
            badges: res.data.badges
        });
    })
    .catch(() => {
        vscode.window.showErrorMessage('LiveCode Mentor: Backend not reachable!');
    });

    // FR1: Monitor changes
    const changeDisposable = vscode.workspace.onDidChangeTextDocument((event) => {
        if (event.document.uri.scheme !== 'file') { return; }
        clearTimeout(debounceTimer);
        sidebarProvider.showLoading();
        debounceTimer = setTimeout(() => {
            sendCodeToBackend(event.document, 'change');
        }, 1500);
    });

    // FR2: Capture on save
    const saveDisposable = vscode.workspace.onDidSaveTextDocument((document) => {
        if (document.uri.scheme !== 'file') { return; }
        clearTimeout(debounceTimer);
        sendCodeToBackend(document, 'save');
    });

    context.subscriptions.push(changeDisposable, saveDisposable);
}

async function sendCodeToBackend(document: vscode.TextDocument, trigger: string) {
    const code = document.getText();
    const language = document.languageId;
    if (code.trim().length === 0) { return; }

    //console.log(`[LiveCode Mentor] Sending code (trigger: ${trigger})`);

    try {
        const res = await axios.post(`${BACKEND_URL}/analyze`, {
            code, language, trigger
        });

        // Update explanation tab
        sidebarProvider.sendMessage('explanation', res.data);

        // Don't show any extra features if there's an error
        if (res.data.has_error) {
            sidebarProvider.sendMessage('recommendations', { leetcode: [], article: null });
            sidebarProvider.sendMessage('autotest', { tests: [] });
            sidebarProvider.sendMessage('hint', { has_mistake: false });
            console.log('[LiveCode Mentor] Error detected — skipping hints/tests/recommendations');
            return;
        }

        // Learning mode only features
        if (currentMode === 'learning') {
            // FR14 + FR15: Recommendations
            if (res.data.concepts && res.data.concepts.length > 0) {
                try {
                    const recRes = await axios.post(`${BACKEND_URL}/recommendations`, {
                        code, language, trigger
                    });
                    sidebarProvider.sendMessage('recommendations', recRes.data);
                } catch (e) {
                    console.error('[LiveCode Mentor] Recommendations error:', e);
                }
            }

            // FR9 + FR10: Hints
            if (res.data.mistake && res.data.mistake.has_mistake) {
                lastMistake = res.data.mistake.mistake;
                try {
                    const hintRes = await axios.post(`${BACKEND_URL}/hint`, {
                        code, language,
                        mistake_type: res.data.mistake.mistake.description
                    });
                    sidebarProvider.sendMessage('hint', hintRes.data);
                } catch (e) {
                    console.error('[LiveCode Mentor] Hint error:', e);
                }
            } else {
                sidebarProvider.sendMessage('hint', { has_mistake: false });
            }
        } else {
            sidebarProvider.sendMessage('hint', { has_mistake: false });
            sidebarProvider.sendMessage('recommendations', { leetcode: [], article: null });
        }

        // FR8: Auto test on save only
        if (trigger === 'save') {
            try {
                const testRes = await axios.post(`${BACKEND_URL}/auto-test`, {
                    code, language, trigger
                });
                sidebarProvider.sendMessage('autotest', testRes.data);
            } catch (e) {
                console.error('[LiveCode Mentor] Auto test error:', e);
            }
        }

        console.log('[LiveCode Mentor] Sidebar updated!');
    } catch (e) {
        console.error('[LiveCode Mentor] Backend error:', e);
    }
}

export function deactivate() {
    clearTimeout(debounceTimer);
}