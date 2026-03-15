import sys

with open('app/apps/[workflowId]/page.tsx', 'r') as f:
    content = f.read()

replacement_ui = '''                    <div className="p-8">
                        {/* Toggle Batch Mode */}
                        <div className="flex justify-center mb-8 bg-slate-100 p-1 rounded-xl max-w-sm mx-auto shadow-inner">
                            <button onClick={() => setIsBatchMode(false)} className={`flex-1 py-2 text-sm font-bold rounded-lg transition-all ${!isBatchMode ? 'bg-white shadow text-blue-600' : 'text-slate-500 hover:text-slate-700'}`}>
                                Single Run
                            </button>
                            <button onClick={() => setIsBatchMode(true)} className={`flex-1 py-2 text-sm font-bold rounded-lg transition-all ${isBatchMode ? 'bg-white shadow text-blue-600' : 'text-slate-500 hover:text-slate-700'}`}>
                                Batch CSV Run
                            </button>
                        </div>

                        {isBatchMode ? (
                            <div className="space-y-6 mb-8">
                                <label className="block text-sm font-bold text-slate-700 mb-2">Upload CSV Dataset</label>
                                <div className="w-full px-4 py-8 bg-slate-50 border-2 border-dashed border-slate-300 rounded-xl hover:bg-slate-100 hover:border-blue-400 transition-all text-center">
                                    <input type="file" accept=".csv" className="hidden" id="csv-upload" onChange={(e) => {
                                        const file = e.target.files?.[0];
                                        if (file) {
                                            Papa.parse(file, {
                                                header: true,
                                                skipEmptyLines: true,
                                                complete: (results) => {
                                                    if (results.data && results.data.length > 0) {
                                                        setCsvData(results.data);
                                                        setCsvHeaders(Object.keys(results.data[0]));
                                                    }
                                                },
                                                error: (err) => alert(err.message)
                                            });
                                        }
                                    }} />
                                    <label htmlFor="csv-upload" className="cursor-pointer flex flex-col items-center justify-center text-slate-500">
                                        <UploadCloud size={32} className="mb-2 text-blue-500"/>
                                        <span className="font-medium text-slate-700">{csvData.length > 0 ? `${csvData.length} Rows Loaded` : 'Click to Upload CSV'}</span>
                                    </label>
                                </div>

                                {csvHeaders.length > 0 && inputs.length > 0 && (
                                    <div className="mt-6">
                                        <h4 className="font-bold text-slate-700 mb-3">Map CSV Columns to Inputs</h4>
                                        <div className="space-y-3 bg-white border border-slate-200 rounded-lg p-4 shadow-sm">
                                            {inputs.map((inp, idx) => (
                                                <div key={idx} className="flex items-center justify-between gap-4">
                                                    <span className="text-sm font-bold text-slate-600">{inp.label}</span>
                                                    <select
                                                        className="px-3 py-2 bg-slate-50 border border-slate-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500"
                                                        value={columnMapping[inp.id] || ""}
                                                        onChange={(e) => setColumnMapping({...columnMapping, [inp.id]: e.target.value})}
                                                    >
                                                        <option value="">-- Select Column --</option>
                                                        {csvHeaders.map(h => <option key={h} value={h}>{h}</option>)}
                                                    </select>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {isExecuting && batchProgress.total > 0 && (
                                    <div className="w-full mt-4">
                                        <div className="flex justify-between text-xs text-slate-500 font-bold mb-1">
                                            <span>Batch Progress</span>
                                            <span>{batchProgress.current} / {batchProgress.total}</span>
                                        </div>
                                        <div className="w-full h-2 bg-slate-200 rounded-full overflow-hidden">
                                            <div className="h-full bg-blue-500 transition-all duration-300" style={{ width: `${(batchProgress.current / batchProgress.total) * 100}%` }}></div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="space-y-6 mb-8">
                                {inputs.length === 0 ? (
                                    <p className="text-slate-500 text-center mb-8">This app requires no inputs. Ready to run.</p>
                                ) : (
                                    inputs.map((inp, idx) => (
                                        <div key={idx}>
                                            <label className="block text-sm font-bold text-slate-700 mb-2">{inp.label}</label>
                                            <textarea
                                                value={inputValues[inp.id] || ""}
                                                onChange={e => setInputValues({...inputValues, [inp.id]: e.target.value})}
                                                className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all resize-none h-24 text-slate-800 shadow-inner"
                                                placeholder="Enter value here..."
                                            />
                                        </div>
                                    ))
                                )}
                            </div>
                        )}'''

target_ui = '''                    <div className="p-8">
                        {inputs.length === 0 ? (
                            <p className="text-slate-500 text-center mb-8">This app requires no inputs. Ready to run.</p>
                        ) : (
                            <div className="space-y-6 mb-8">
                                {inputs.map((inp, idx) => (
                                    <div key={idx}>
                                        <label className="block text-sm font-bold text-slate-700 mb-2">{inp.label}</label>
                                        <textarea
                                            value={inputValues[inp.id]}
                                            onChange={e => setInputValues({...inputValues, [inp.id]: e.target.value})}
                                            className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all resize-none h-24 text-slate-800"
                                            placeholder="Enter value here..."
                                        />
                                    </div>
                                ))}
                            </div>
                        )}'''

content = content.replace(target_ui, replacement_ui)

with open('app/apps/[workflowId]/page.tsx', 'w') as f:
    f.write(content)
