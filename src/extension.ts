import * as vscode from 'vscode';
import axios from 'axios';
import { SidebarProvider } from './SidebarProvider';

const BACKEND_URL = 'http://localhost:8000';
let debounceTimer: ReturnType<typeof setTimeout>;
let sidebarProvider: SidebarProvider;

export function activate(context: vscode.ExtensionContext) {
    console.log('LiveCode Mentor is now active!');

    // Register sidebar
    sidebarProvider = new SidebarProvider(context.extensionUri);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider('livecodeMentor', sidebarProvider)
    );

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('livecode-mentor.generateFlow', () => {
            const editor = vscode.window.activeTextEditor;
            if (editor) { sendCodeToBackend(editor.document, 'flow'); }
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('livecode-mentor.checkFix', () => {
            const editor = vscode.window.activeTextEditor;
            if (editor) { sendCodeToBackend(editor.document, 'checkfix'); }
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
        // Send result to sidebar
        sidebarProvider.sendMessage('explanation', res.data);
        console.log('[LiveCode Mentor] Sidebar updated!');
    } catch (e) {
        console.error('[LiveCode Mentor] Backend error:', e);
    }
}

export function deactivate() {
    clearTimeout(debounceTimer);
}