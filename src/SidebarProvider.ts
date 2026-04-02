import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

export class SidebarProvider implements vscode.WebviewViewProvider {
    private _view?: vscode.WebviewView;

    constructor(private readonly _extensionUri: vscode.Uri) {}

    public resolveWebviewView(webviewView: vscode.WebviewView) {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [
                vscode.Uri.joinPath(this._extensionUri, 'media')
            ]
        };

        webviewView.webview.html = this._getHtmlContent(webviewView.webview);

        webviewView.webview.onDidReceiveMessage(message => {
            if (message.type === 'requestFlow') {
                vscode.commands.executeCommand('livecode-mentor.generateFlow');
            } else if (message.type === 'checkFix') {
                vscode.commands.executeCommand('livecode-mentor.checkFix');
            } else if (message.type === 'requestTrace') {
                vscode.commands.executeCommand('livecode-mentor.generateTrace');
            } else if (message.type === 'openLink') {
                vscode.env.openExternal(vscode.Uri.parse(message.url));
            } else if (message.type === 'setMode') {
                vscode.commands.executeCommand('livecode-mentor.setMode', message.mode);
            } else if (message.type === 'reanalyze') {
                vscode.commands.executeCommand('livecode-mentor.reanalyze');
            } else if (message.type === 'switchTab') {
                // switchTab is handled in sidebar.html JS — just pass it through
            }
        });
    }

    public sendMessage(type: string, data: unknown) {
        if (this._view) {
            this._view.webview.postMessage({ type, data });
        }
    }

    public showLoading() {
        if (this._view) {
            this._view.webview.postMessage({ type: 'loading' });
        }
    }

    private _getHtmlContent(webview: vscode.Webview): string {
        const htmlPath = path.join(this._extensionUri.fsPath, 'media', 'sidebar.html');
        return fs.readFileSync(htmlPath, 'utf8');
    }
}