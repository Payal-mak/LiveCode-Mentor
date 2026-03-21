import * as vscode from 'vscode';
import axios from 'axios';
import { SidebarProvider } from './SidebarProvider';

const BACKEND_URL = 'http://localhost:8000';
let debounceTimer: ReturnType<typeof setTimeout>;
let sidebarProvider: SidebarProvider;
let lastMistake: { type: string; description: string } | null = null;
let currentMode: string = 'learning'; // FR17: track mode

export function activate(context: vscode.ExtensionContext) {
    console.log('LiveCode Mentor is now active!');

    sidebarProvider = new SidebarProvider(context.extensionUri);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider('livecodeMentor', sidebarProvider)
    );

    // Generate flow command
    context.subscriptions.push(
        vscode.commands.registerCommand('livecode-mentor.generateFlow', () => {
            const editor = vscode.window.activeTextEditor;
            if (editor) { sendCodeToBackend(editor.document, 'flow'); }
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
                    vscode.window.showInformationMessage('Great job! Issue resolved! 🎉');
                } else {
                    vscode.window.showWarningMessage('Not quite — check the hint again!');
                }
            } catch (e) {
                console.error(e);
            }
        })
    );

    // Health check
    axios.get(`${BACKEND_URL}/health`)
        .then(res => {
            vscode.window.showInformationMessage(`LiveCode Mentor: ${res.data.status}`);
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

    console.log(`[LiveCode Mentor] Sending code (trigger: ${trigger})`);

    try {
        const res = await axios.post(`${BACKEND_URL}/analyze`, {
            code, language, trigger
        });

        // Update explanation tab
        sidebarProvider.sendMessage('explanation', res.data);

        // FR14 + FR15: Get recommendations
        if (!res.data.has_error && res.data.concepts && res.data.concepts.length > 0) {
            try {
                const recRes = await axios.post(`${BACKEND_URL}/recommendations`, {
                code, language, trigger
            });
            sidebarProvider.sendMessage('recommendations', recRes.data);
            } catch (e) {
        console.error('[LiveCode Mentor] Recommendations error:', e);
            }
        }

        // FR8: Auto test on save
        if (trigger === 'save' && !res.data.has_error) {
            try {
                const testRes = await axios.post(`${BACKEND_URL}/auto-test`, {
                    code, language, trigger
                });
                sidebarProvider.sendMessage('autotest', testRes.data);
            } catch (e) {
                console.error('[LiveCode Mentor] Auto test error:', e);
            }
        }

        // FR10: If mistake detected, get hint
        if (res.data.mistake && res.data.mistake.has_mistake) {
            lastMistake = res.data.mistake.mistake;
            const hintRes = await axios.post(`${BACKEND_URL}/hint`, {
                code,
                language,
                mistake_type: res.data.mistake.mistake.description
            });
            sidebarProvider.sendMessage('hint', hintRes.data);
        } else {
            sidebarProvider.sendMessage('hint', { has_mistake: false });
        }

        console.log('[LiveCode Mentor] Sidebar updated!');
    } catch (e) {
        console.error('[LiveCode Mentor] Backend error:', e);
    }
}

export function deactivate() {
    clearTimeout(debounceTimer);
}