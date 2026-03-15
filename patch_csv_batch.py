import sys
import re

with open('app/apps/[workflowId]/page.tsx', 'r') as f:
    content = f.read()

# Add imports and new state variables
import_target = '''import { Play, Bot, ArrowLeft, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { Node, Edge } from '@xyflow/react';'''
import_replacement = '''import { Play, Bot, ArrowLeft, Loader2, CheckCircle2, AlertCircle, UploadCloud, Copy, Download } from 'lucide-react';
import { Node, Edge } from '@xyflow/react';
import Papa from 'papaparse';'''

content = content.replace(import_target, import_replacement)

state_target = '''    const [isExecuting, setIsExecuting] = useState(false);'''
state_replacement = '''    const [isBatchMode, setIsBatchMode] = useState(false);
    const [csvData, setCsvData] = useState<any[]>([]);
    const [csvHeaders, setCsvHeaders] = useState<string[]>([]);
    const [columnMapping, setColumnMapping] = useState<Record<string, string>>({}); // workflowInputId -> csvHeader
    const [batchProgress, setBatchProgress] = useState({ current: 0, total: 0 });

    const [isExecuting, setIsExecuting] = useState(false);'''

content = content.replace(state_target, state_replacement)


# Add handleBatchRun
handle_run_target = '''    const handleRun = async () => {'''
handle_run_replacement = '''    const executeSingleRun = async (overrideValues: Record<string, string>) => {
        return new Promise((resolve, reject) => {
            const updatedNodes = nodes.map(n => {
                const override = overrideValues[n.id];
                if (override !== undefined && override !== "") {
                    if (n.type === 'scraper' || n.type === 'agentic_loop' || n.type === 'webhook') {
                        return { ...n, data: { ...n.data, url: override }};
                    }
                    if (n.type === 'gemini') {
                        return { ...n, data: { ...n.data, prompt: override }};
                    }
                }
                return n;
            });

            let compiledData;
            try {
                compiledData = compileNodesToSteps(updatedNodes, edges);
            } catch (err: any) {
                reject(err.message || "Failed to compile workflow");
                return;
            }

            fetch("http://127.0.0.1:5000/execute", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ steps: compiledData.steps, nodeOrder: compiledData.nodeOrder, user_id: currentUserId }),
            }).then(async (response) => {
                if (!response.ok) {
                    const errData = await response.json();
                    reject(new Error(errData.error || "Failed to start execution"));
                    return;
                }

                const data = await response.json();
                const taskId = data.task_id;

                const eventSource = new EventSource(`http://127.0.0.1:5000/api/logs/${taskId}`);

                eventSource.onmessage = async (event) => {
                    if (event.data === "__DONE__") {
                        eventSource.close();
                        resolve(true);
                        return;
                    }
                    try {
                        const parsed = JSON.parse(event.data);
                        if (parsed.error) {
                            setLogs(prev => [...prev, { status: "Error", message: parsed.error }]);
                            eventSource.close();
                            resolve(false);
                            return;
                        }
                        if (parsed.status) {
                            setLogs(prev => [...prev, { status: parsed.status, message: parsed.message || parsed.result || "" }]);
                        }
                        if (parsed.status === 'Workflow Finished' || parsed.status === 'Error' || parsed.status === 'Canceled') {
                            eventSource.close();
                            resolve(parsed.status === 'Workflow Finished');
                        }
                    } catch(e) {}
                };

                eventSource.onerror = () => {
                    eventSource.close();
                    resolve(false);
                };
            }).catch(reject);
        });
    };

    const handleBatchRun = async () => {
        if (csvData.length === 0) { alert("Please upload a valid CSV first."); return; }

        setIsExecuting(true);
        setLogs([]);
        setBatchProgress({ current: 0, total: csvData.length });

        for (let i = 0; i < csvData.length; i++) {
            const row = csvData[i];

            // Build override values for this specific row based on mapping
            const rowOverrides: Record<string, string> = {};
            for (const inputId of Object.keys(columnMapping)) {
                const headerName = columnMapping[inputId];
                if (headerName && row[headerName] !== undefined) {
                    rowOverrides[inputId] = row[headerName];
                }
            }

            setLogs(prev => [...prev, { status: "Batch", message: `--- Starting Row ${i + 1} of ${csvData.length} ---` }]);
            setBatchProgress({ current: i + 1, total: csvData.length });

            try {
                const success = await executeSingleRun(rowOverrides);
                if (!success) {
                    setLogs(prev => [...prev, { status: "Batch Error", message: `Row ${i + 1} Failed. Continuing to next row...` }]);
                }
            } catch (err: any) {
                setLogs(prev => [...prev, { status: "Batch Error", message: `Row ${i + 1} Threw Exception: ${err.message}. Continuing...` }]);
            }
        }

        setLogs(prev => [...prev, { status: "Batch Complete", message: "--- All rows processed ---" }]);
        setIsExecuting(false);
        fetchRecentRuns(workflowId);
    };

    const handleRun = async () => {
        if (isBatchMode) {
            await handleBatchRun();
            return;
        }

        setIsExecuting(true);
        setLogs([]);
        try {
            await executeSingleRun(inputValues);
        } catch (e: any) {
            alert(e.message);
        }
        setIsExecuting(false);
        fetchRecentRuns(workflowId);
    };

    /* Legacy Handle Run implementation replaced above */
'''

# Find the end of handleRun to replace it entirely
def replace_handle_run(text):
    start_idx = text.find("const handleRun = async () => {")
    end_idx = text.find("if (!workflow) return", start_idx)
    return text[:start_idx] + handle_run_replacement + text[end_idx:]

content = replace_handle_run(content)

with open('app/apps/[workflowId]/page.tsx', 'w') as f:
    f.write(content)
