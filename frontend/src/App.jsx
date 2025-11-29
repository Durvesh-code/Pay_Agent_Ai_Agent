import React, { useState, useEffect } from 'react';

// LiveMonitor Component
// LiveMonitor Component
function LiveMonitor({ transaction, onClose, token }) {
  const [imageUrl, setImageUrl] = useState(`http://localhost:8000/static/live_feed.png`);
  const [pin, setPin] = useState("");
  const [status, setStatus] = useState(transaction.status);

  useEffect(() => {
    const interval = setInterval(async () => {
        // Poll Status
        try {
            const res = await fetch(`http://localhost:8000/transactions/${transaction.id}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            
            if (res.status === 401) {
                localStorage.removeItem('token');
                window.location.reload();
                return;
            }

            if (res.ok) {
                const data = await res.json();
                setStatus(data.status);
                
                // Refresh Image with timestamp to bypass cache
                // We use the transaction ID to ensure unique feed if supported, or fallback to generic
                setImageUrl(`http://localhost:8000/static/live_feed.png?t=${Date.now()}`);
                
                if (data.status === 'PAID') {
                    setTimeout(onClose, 3000); // Close after 3s success
                }
            }
        } catch (e) {
            console.error("Polling error", e);
        }
    }, 1000);
    return () => clearInterval(interval);
  }, [transaction.id, token, onClose]);

  const submitPin = async () => {
     try {
         const res = await fetch(`http://localhost:8000/transactions/${transaction.id}/provide_pin`, {
             method: 'POST',
             headers: {
                 'Content-Type': 'application/json',
                 'Authorization': `Bearer ${token}`
             },
             body: JSON.stringify({pin})
         });
         
         if (res.status === 401) {
             localStorage.removeItem('token');
             window.location.reload();
             return;
         }

         setPin(""); // Clear pin
     } catch (e) {
         console.error("Failed to submit PIN", e);
     }
  };

  return (
    <div className="fixed inset-0 bg-black/90 z-50 flex items-center justify-center p-4 backdrop-blur-sm">
        <div className="w-full max-w-5xl bg-gray-900 rounded-2xl overflow-hidden border border-gray-700 shadow-2xl relative">
            {/* Header */}
            <div className="p-4 bg-gray-800 flex justify-between items-center border-b border-gray-700">
                <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-red-500 animate-pulse"></span>
                    <h3 className="text-white font-mono font-bold tracking-wider">LIVE AGENT FEED</h3>
                </div>
                <div className="flex items-center gap-4">
                    <span className={`px-3 py-1 rounded text-xs font-bold font-mono ${
                        status === 'WAITING_FOR_PIN' ? 'bg-yellow-500/20 text-yellow-400 animate-pulse' :
                        status === 'PAID' ? 'bg-green-500/20 text-green-400' :
                        'bg-blue-500/20 text-blue-400'
                    }`}>
                        {status.replace(/_/g, ' ')}
                    </span>
                    <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                    </button>
                </div>
            </div>

            {/* Live Feed Area */}
            <div className="relative aspect-video bg-black flex items-center justify-center">
                <img src={imageUrl} className="w-full h-full object-contain" alt="Agent View" />
                
                {/* PIN Overlay */}
                {status === 'WAITING_FOR_PIN' && (
                    <div className="absolute inset-0 bg-black/60 backdrop-blur-md flex items-center justify-center animate-fade-in">
                        <div className="bg-white p-8 rounded-2xl shadow-2xl text-center max-w-md w-full transform scale-100 transition-all">
                            <div className="w-16 h-16 bg-blue-50 rounded-full flex items-center justify-center mx-auto mb-6">
                                <span className="text-3xl">🔒</span>
                            </div>
                            <h3 className="text-2xl font-bold text-gray-900 mb-2">Security Check</h3>
                            <p className="text-gray-500 mb-6 text-sm">The agent requires your authorization to proceed with the payment.</p>
                            
                            <input 
                                type="password" 
                                value={pin}
                                onChange={(e) => setPin(e.target.value)}
                                placeholder="Enter 6-digit PIN"
                                maxLength={6}
                                className="w-full text-center text-3xl tracking-[0.5em] font-mono border-2 border-gray-200 rounded-xl p-4 mb-6 focus:border-blue-500 focus:ring-4 focus:ring-blue-500/20 outline-none transition-all"
                                autoFocus
                            />
                            
                            <button 
                                onClick={submitPin}
                                disabled={pin.length < 4}
                                className="w-full bg-blue-600 text-white py-4 rounded-xl font-bold text-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-blue-200"
                            >
                                AUTHORIZE PAYMENT
                            </button>
                        </div>
                    </div>
                )}

                {/* Success Overlay */}
                {status === 'PAID' && (
                    <div className="absolute inset-0 bg-green-500/20 backdrop-blur-sm flex items-center justify-center animate-fade-in">
                        <div className="bg-white p-8 rounded-2xl shadow-2xl text-center">
                            <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                                <svg className="w-10 h-10 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>
                            </div>
                            <h3 className="text-2xl font-bold text-gray-900">Payment Successful!</h3>
                            <p className="text-gray-500 mt-2">Redirecting...</p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    </div>
  );
}

function LoginScreen({ onLogin }) {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError("");
        
        const formData = new FormData();
        formData.append('username', email);
        formData.append('password', password);

        try {
            const res = await fetch('http://localhost:8000/token', {
                method: 'POST',
                body: formData
            });
            
            if (res.ok) {
                const data = await res.json();
                onLogin(data.access_token);
            } else {
                setError("Invalid credentials");
            }
        } catch (e) {
            setError("Login failed");
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-100">
            <div className="bg-white p-8 rounded-2xl shadow-xl w-full max-w-md">
                <div className="text-center mb-8">
                    <h1 className="text-3xl font-extrabold text-blue-600 mb-2">PayAgent</h1>
                    <p className="text-gray-500">Sign in to your account</p>
                </div>
                
                {error && (
                    <div className="bg-red-50 text-red-600 p-3 rounded-lg mb-4 text-sm text-center">
                        {error}
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-6">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Email Address</label>
                        <input 
                            type="email" 
                            required
                            value={email}
                            onChange={e => setEmail(e.target.value)}
                            className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                            placeholder="admin@example.com"
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
                        <input 
                            type="password" 
                            required
                            value={password}
                            onChange={e => setPassword(e.target.value)}
                            className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                            placeholder="••••••••"
                        />
                    </div>
                    <button 
                        type="submit"
                        className="w-full bg-blue-600 text-white py-3 rounded-xl font-bold hover:bg-blue-700 transition-colors"
                    >
                        Sign In
                    </button>
                </form>
                <div className="mt-6 text-center text-xs text-gray-400">
                    Use admin@example.com / password for demo
                </div>
            </div>
        </div>
    );
}

function App() {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [activeTab, setActiveTab] = useState('upload');
  const [transactions, setTransactions] = useState([]);
  const [monitoringTransaction, setMonitoringTransaction] = useState(null);
  const [loadingQueue, setLoadingQueue] = useState(false);
  const [isPolling, setIsPolling] = useState(false);

  useEffect(() => {
      if (token) {
          localStorage.setItem('token', token);
      } else {
          localStorage.removeItem('token');
      }
  }, [token]);

  useEffect(() => {
    let interval;
    if (activeTab === 'queue' && token) {
      fetchTransactions();
      // Poll if we are expecting data
      if (isPolling) {
          interval = setInterval(fetchTransactions, 2000);
      }
    }
    return () => clearInterval(interval);
  }, [activeTab, token, isPolling]);

  const fetchTransactions = async () => {
    if (!isPolling) setLoadingQueue(true);
    try {
      const response = await fetch('http://localhost:8000/transactions/pending', {
          headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.status === 401) {
          setToken(null);
          return;
      }
      if (response.ok) {
          const data = await response.json();
          setTransactions(data);
          if (data.length > 0 && isPolling) {
              setIsPolling(false); // Stop polling once we find data
          }
      }
    } catch (error) {
      console.error('Error fetching transactions:', error);
    } finally {
      if (!isPolling) setLoadingQueue(false);
    }
  };

  const approveTransaction = async (id) => {
    try {
      if (id === 'ALL') {
          // Approve Batch
          if (transactions.length === 0) return;
          const batchId = transactions[0].batch_id; 
          
          const response = await fetch(`http://localhost:8000/transactions/approve_batch/${batchId}`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
          });
          
          if (response.status === 401) {
              setToken(null);
              return;
          }
          
          if (response.ok) {
              const data = await response.json();
              if (data.task_ids && data.task_ids.length > 0) {
                  await fetchTransactions();
                  alert(`Batch approved! ${data.count} transactions queued.`);
              }
          }
      } else {
          // Check if already processing
          const tx = transactions.find(t => t.id === id);
          if (tx && (tx.status === 'WAITING_FOR_PIN' || tx.status === 'QUEUED_FOR_PAYMENT')) {
              setMonitoringTransaction(tx);
              return;
          }

          // Single Approve
          const response = await fetch(`http://localhost:8000/transactions/${id}/approve`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
          });

          if (response.status === 401) {
              setToken(null);
              return;
          }

          if (response.ok) {
            setMonitoringTransaction({ id, status: 'QUEUED_FOR_PAYMENT' });
            fetchTransactions();
          }
      }
    } catch (error) {
      console.error('Error approving transaction:', error);
    }
  };

  const updateTransaction = async (id, updates) => {
    try {
      const res = await fetch(`http://localhost:8000/transactions/${id}`, {
        method: 'PUT',
        headers: { 
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(updates)
      });
      
      if (res.status === 401) {
          setToken(null);
          return;
      }

      fetchTransactions();
    } catch (error) {
      console.error('Error updating transaction:', error);
    }
  };

  if (!token) {
      return <LoginScreen onLogin={setToken} />;
  }

  return (
    <div className="flex h-screen bg-gray-50 font-sans text-gray-900">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-6 border-b border-gray-200">
          <h1 className="text-2xl font-extrabold bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-indigo-600">
            PayAgent
          </h1>
          <p className="text-xs text-gray-500 mt-1">Autonomous Finance</p>
        </div>
        
        <nav className="flex-1 p-4 space-y-2">
          <SidebarItem icon="📤" label="Upload Statement" active={activeTab === 'upload'} onClick={() => setActiveTab('upload')} />
          <SidebarItem icon="📋" label="Verification Queue" active={activeTab === 'queue'} onClick={() => setActiveTab('queue')} />
          <SidebarItem icon="📜" label="Audit Logs" active={activeTab === 'audits'} onClick={() => setActiveTab('audits')} />
        </nav>

        <div className="p-4 border-t border-gray-200">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center text-green-600 font-bold text-xs">
              AG
            </div>
            <div>
              <p className="text-sm font-medium">Agent Status</p>
              <p className="text-xs text-green-600 flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-green-500"></span>
                Online
              </p>
            </div>
          </div>
          <button 
            onClick={() => setToken(null)}
            className="w-full py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors"
          >
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto">
        <header className="bg-white border-b border-gray-200 px-8 py-5 flex justify-between items-center sticky top-0 z-10">
          <h2 className="text-xl font-bold text-gray-800">
            {activeTab === 'upload' && 'Upload Statement / Invoice'}
            {activeTab === 'queue' && 'Verification Queue'}
            {activeTab === 'audits' && 'Audit Logs'}
          </h2>
          <div className="flex gap-4">
             <button className="p-2 text-gray-400 hover:text-gray-600">🔔</button>
             <button className="p-2 text-gray-400 hover:text-gray-600">⚙️</button>
          </div>
        </header>

        <div className="p-8">
          {activeTab === 'upload' && (
              <UploadSection 
                  token={token} 
                  onUploadSuccess={() => {
                      setActiveTab('queue');
                      setIsPolling(true);
                  }} 
              />
          )}
          {activeTab === 'queue' && (
            <TransactionQueue 
                transactions={transactions} 
                onApprove={approveTransaction} 
                onUpdate={updateTransaction}
                loading={loadingQueue || isPolling}
            />
          )}
          {activeTab === 'audits' && <AuditLog token={token} />}
        </div>
      </main>

      {/* Live Monitor Modal */}
      {monitoringTransaction && (
        <LiveMonitor 
            transaction={monitoringTransaction} 
            onClose={() => setMonitoringTransaction(null)} 
            token={token}
        />
      )}
    </div>
  );
}

function SidebarItem({ icon, label, active, onClick }) {
  return (
    <button 
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 ${
        active 
          ? 'bg-blue-50 text-blue-700 shadow-sm ring-1 ring-blue-100' 
          : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
      }`}
    >
      <span className="text-lg">{icon}</span>
      <span className="font-medium text-sm">{label}</span>
      {active && <span className="ml-auto w-1.5 h-1.5 rounded-full bg-blue-600"></span>}
    </button>
  );
}

function UploadSection({ token, onUploadSuccess }) {
    const [file, setFile] = useState(null);
    const [uploading, setUploading] = useState(false);
    const [status, setStatus] = useState(null);

    const handleUpload = async () => {
        if (!file) return;
        setUploading(true);
        setStatus('uploading');
        
        const formData = new FormData();
        formData.append('file', file);

        try {
            const res = await fetch('http://localhost:8000/upload', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData
            });
            
            if (res.status === 401) {
                // Token expired
                localStorage.removeItem('token');
                window.location.reload(); // Force reload to clear state/token
                return;
            }

            const data = await res.json();
            setStatus('success');
            console.log(data);
            setTimeout(() => {
                onUploadSuccess();
            }, 1000);
        } catch (e) {
            setStatus('error');
            console.error(e);
        } finally {
            setUploading(false);
        }
    };

    return (
        <div className="max-w-2xl mx-auto">
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8 text-center">
                <div className="w-20 h-20 bg-blue-50 rounded-full flex items-center justify-center mx-auto mb-6">
                    <span className="text-4xl">📄</span>
                </div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">Upload Invoice, Statement, or Handwritten Note</h3>
                <p className="text-gray-500 mb-4">Supports PDF invoices, bulk statements, and images.</p>
                <div className="inline-block bg-blue-100 text-blue-800 text-xs font-bold px-3 py-1 rounded-full mb-8">
                    Universal Extraction Engine
                </div>
                
                <input 
                    type="file" 
                    onChange={e => setFile(e.target.files[0])}
                    className="block w-full text-sm text-gray-500 file:mr-4 file:py-2.5 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 mb-6 cursor-pointer"
                />

                <button 
                    onClick={handleUpload}
                    disabled={!file || uploading}
                    className="w-full bg-blue-600 text-white py-3 rounded-xl font-bold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-blue-200"
                >
                    {uploading ? 'Processing...' : 'Process Document'}
                </button>

                {status === 'success' && (
                    <div className="mt-6 p-4 bg-green-50 text-green-700 rounded-xl flex items-center justify-center gap-2 animate-fade-in">
                        <span>✅</span> Document uploaded and processing started!
                    </div>
                )}
            </div>
        </div>
    );
}

function TransactionQueue({ transactions, onApprove, onUpdate, loading }) {
    const [approvingBatch, setApprovingBatch] = useState(false);

    const handleApproveAll = async () => {
        if (transactions.length === 0) return;
        
        // Assume all pending transactions belong to the same batch or we just approve the batch of the first one
        // Ideally, we should have a batch_id available. Let's check if transactions have batch_id.
        // Based on backend, they do.
        const batchId = transactions[0].batch_id;
        if (!batchId) {
            alert("No batch ID found for transactions.");
            return;
        }

        if (!confirm(`Are you sure you want to approve all ${transactions.length} transactions?`)) return;

        setApprovingBatch(true);
        try {
            // We need the token here. But this component doesn't have it directly.
            // We should pass a handler from parent or use context. 
            // For now, let's assume onApprove can handle a special 'all' case or we pass a new prop.
            // Actually, let's just add a new prop 'onApproveBatch' to keep it clean.
            // But wait, I can't change the parent in this single replace block easily without changing App component too.
            // Let's modify App component to pass onApproveBatch.
        } catch (e) {
            console.error(e);
        } finally {
            setApprovingBatch(false);
        }
    };

    return (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
            <div className="p-4 border-b border-gray-200 flex justify-between items-center bg-gray-50">
                <h3 className="font-bold text-gray-700">Pending Transactions</h3>
                {transactions.length > 0 && (
                    <button 
                        onClick={() => onApprove('ALL')} 
                        className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-6 py-2 rounded-lg text-sm font-bold hover:shadow-lg hover:scale-105 transition-all flex items-center gap-2 animate-pulse-slow"
                    >
                        <span className="text-lg">✓</span> APPROVE ALL ({transactions.length})
                    </button>
                )}
            </div>
            <table className="w-full text-left border-collapse">
                <thead>
                    <tr className="bg-gray-50 border-b border-gray-200">
                        <th className="p-4 text-xs font-bold text-gray-500 uppercase tracking-wider">Vendor</th>
                        <th className="p-4 text-xs font-bold text-gray-500 uppercase tracking-wider">Amount</th>
                        <th className="p-4 text-xs font-bold text-gray-500 uppercase tracking-wider">Account</th>
                        <th className="p-4 text-xs font-bold text-gray-500 uppercase tracking-wider">Status</th>
                        <th className="p-4 text-xs font-bold text-gray-500 uppercase tracking-wider">Action</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                    {transactions.map(tx => {
                        const isReview = tx.status === 'NEEDS_REVIEW';
                        return (
                            <tr key={tx.id} className={`hover:bg-gray-50 transition-colors ${isReview ? 'bg-red-50/30' : ''}`}>
                                <td className="p-4 font-medium text-gray-900">{tx.vendor}</td>
                                <td className="p-4 font-mono text-gray-600">₹{tx.amount}</td>
                                <td className="p-4 text-gray-500 text-sm">
                                    {isReview && !tx.account_number ? (
                                        <input 
                                            type="text" 
                                            placeholder="Enter Account No"
                                            className="border border-red-300 bg-white rounded px-2 py-1 text-sm w-full focus:ring-2 focus:ring-red-500 outline-none shadow-sm animate-pulse-border"
                                            onBlur={(e) => onUpdate(tx.id, { account_number: e.target.value })}
                                        />
                                    ) : (
                                        tx.account_number
                                    )}
                                </td>
                                <td className="p-4">
                                    <span className={`px-2 py-1 rounded-full text-xs font-bold ${
                                        isReview ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'
                                    }`}>
                                        {tx.status.replace(/_/g, ' ')}
                                    </span>
                                </td>
                                <td className="p-4">
                                    <button 
                                        onClick={() => onApprove(tx.id)}
                                        disabled={(isReview && !tx.account_number) || tx.status === 'QUEUED_FOR_PAYMENT' || tx.status === 'WAITING_FOR_PIN'}
                                        className="px-4 py-2 bg-black text-white rounded-lg text-sm font-bold hover:bg-gray-800 transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        {tx.status === 'QUEUED_FOR_PAYMENT' ? 'Processing...' : 
                                         tx.status === 'WAITING_FOR_PIN' ? 'Enter PIN' : 
                                         'Approve & Pay'}
                                    </button>
                                </td>
                            </tr>
                        );
                    })}
                    {transactions.length === 0 && (
                        <tr>
                            <td colSpan="5" className="p-12 text-center text-gray-500">
                                {loading ? (
                                    <div className="flex flex-col items-center gap-3">
                                        <svg className="animate-spin h-8 w-8 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                        </svg>
                                        <p className="font-medium text-gray-600">Processing your document...</p>
                                        <p className="text-xs text-gray-400">This usually takes 10-20 seconds.</p>
                                    </div>
                                ) : (
                                    "No pending transactions found."
                                )}
                            </td>
                        </tr>
                    )}
                </tbody>
            </table>
        </div>
    );
}

function AuditLog({ token }) {
    const [audits, setAudits] = useState([]);

    useEffect(() => {
        if (token) {
            fetch('http://localhost:8000/audits', {
                headers: { 'Authorization': `Bearer ${token}` }
            })
                .then(res => res.json())
                .then(data => setAudits(data))
                .catch(e => console.error(e));
        }
    }, [token]);

    return (
        <div className="space-y-4">
            {audits.map(audit => (
                <div key={audit.id} className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
                    <div className="flex justify-between items-start mb-2">
                        <span className="font-mono text-xs text-gray-400">{audit.created_at}</span>
                        <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs font-mono">
                            {audit.request_hash?.substring(0, 8)}
                        </span>
                    </div>
                    <pre className="text-xs bg-gray-50 p-3 rounded-lg overflow-x-auto text-gray-700 font-mono">
                        {audit.raw_response || "No response data"}
                    </pre>
                </div>
            ))}
        </div>
    );
}

export default App;
