import * as vscode from 'vscode';
import axios from 'axios';

const BACKEND_URL = 'http://localhost:8000';

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
}

export function deactivate() {}