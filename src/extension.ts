import * as vscode from 'vscode';
import axios from 'axios';

const BACKEND_URL = 'http://localhost:8000';
let debounceTimer: ReturnType<typeof setTimeout>;

export function activate(context: vscode.ExtensionContext) {
    console.log('LiveCode Mentor is now active!');

    // Health check on startup
    axios.get(`${BACKEND_URL}/health`)
        .then(res => {
            vscode.window.showInformationMessage(`LiveCode Mentor: ${res.data.status}`);
        })
        .catch(() => {
            vscode.window.showErrorMessage('LiveCode Mentor: Backend not reachable. Start FastAPI server!');
        });

    // FR1: Monitor code changes in real time
    const changeDisposable = vscode.workspace.onDidChangeTextDocument((event) => {
        // Only track code files, ignore output/debug panels
        if (event.document.uri.scheme !== 'file') { return; }

        clearTimeout(debounceTimer);

        // FR2: Wait 1.5s after user stops typing
        debounceTimer = setTimeout(() => {
            sendCodeToBackend(event.document, 'change');
        }, 1500);
    });

    // FR2: Also capture immediately on save
    const saveDisposable = vscode.workspace.onDidSaveTextDocument((document) => {
        if (document.uri.scheme !== 'file') {return;}

        clearTimeout(debounceTimer);
        sendCodeToBackend(document, 'save');
    });

    context.subscriptions.push(changeDisposable, saveDisposable);
}

async function sendCodeToBackend(document: vscode.TextDocument, trigger: string) {
    const code = document.getText();
    const language = document.languageId;
    const fileName = document.fileName;

    // Skip empty files
    if (code.trim().length === 0) {return;}

    console.log(`[LiveCode Mentor] Sending code to backend (trigger: ${trigger})`);

    try {
        const res = await axios.post(`${BACKEND_URL}/analyze`, {
            code,
            language,
            fileName,
            trigger
        });
        console.log(`[LiveCode Mentor] Backend response:`, res.data);
        vscode.window.showInformationMessage(`LiveCode Mentor: ${res.data.message}`);
    } catch (e) {
        console.error('[LiveCode Mentor] Backend error:', e);
    }
}

export function deactivate() {
    clearTimeout(debounceTimer);
}