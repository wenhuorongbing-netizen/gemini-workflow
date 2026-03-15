"use client";
import { useState, useEffect } from 'react';
import { Check, Zap, Sparkles, Building2, ArrowLeft } from 'lucide-react';

export default function PricingPage() {
    const [userId, setUserId] = useState<string>("user1");
    const [isUpgrading, setIsUpgrading] = useState(false);

    useEffect(() => {
        const saved = localStorage.getItem('current_userId');
        if (saved) setUserId(saved);
    }, []);

    const handleUpgrade = async () => {
        setIsUpgrading(true);
        try {
            const res = await fetch('/api/billing/upgrade', {
                method: 'POST',
                headers: { 'x-user-id': userId }
            });
            if (res.ok) {
                alert("Upgrade Successful! 500 Tokens have been added to your balance.");
                window.location.href = "/";
            } else {
                alert("Failed to upgrade.");
            }
        } catch(e) {
            alert("Error connecting to billing service.");
        } finally {
            setIsUpgrading(false);
        }
    };

    return (
        <div className="min-h-screen bg-slate-950 text-white selection:bg-blue-500/30">
            <div className="absolute top-0 w-full h-96 bg-gradient-to-b from-blue-900/20 to-transparent pointer-events-none"></div>

            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-12 pb-24 relative z-10">
                <a href="/" className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white mb-12 font-medium transition-colors">
                    <ArrowLeft size={16}/> Back to Dashboard
                </a>

                <div className="text-center max-w-3xl mx-auto mb-16">
                    <h1 className="text-4xl md:text-6xl font-extrabold tracking-tight mb-6 bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-400">
                        Scale your AI Automations
                    </h1>
                    <p className="text-lg text-slate-400">
                        Choose the perfect plan to orchestrate Gemini bots. No hidden fees, upgrade anytime.
                    </p>
                </div>

                <div className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto items-center">
                    {/* Starter Tier */}
                    <div className="bg-slate-900 rounded-3xl p-8 border border-slate-800 shadow-xl">
                        <div className="mb-6">
                            <h3 className="text-xl font-bold text-slate-300 mb-2 flex items-center gap-2"><Zap size={20} className="text-slate-500"/> Starter</h3>
                            <div className="text-4xl font-extrabold mb-1">$0<span className="text-lg font-normal text-slate-500">/mo</span></div>
                            <p className="text-sm text-slate-400">Perfect for prototyping.</p>
                        </div>
                        <ul className="space-y-4 mb-8 text-sm text-slate-300">
                            <li className="flex items-center gap-3"><Check size={16} className="text-blue-500"/> 5 Tokens per day</li>
                            <li className="flex items-center gap-3"><Check size={16} className="text-blue-500"/> Standard Gemini Flash</li>
                            <li className="flex items-center gap-3"><Check size={16} className="text-blue-500"/> Community Support</li>
                        </ul>
                        <button disabled className="w-full py-3 rounded-xl bg-slate-800 text-slate-400 font-bold border border-slate-700 cursor-not-allowed">
                            Current Plan
                        </button>
                    </div>

                    {/* Pro Tier */}
                    <div className="bg-slate-800 rounded-3xl p-8 border-2 border-blue-500 shadow-2xl shadow-blue-900/20 transform md:-translate-y-4 relative">
                        <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-blue-500 text-white px-4 py-1 rounded-full text-xs font-bold tracking-wider uppercase">
                            Most Popular
                        </div>
                        <div className="mb-6">
                            <h3 className="text-xl font-bold text-white mb-2 flex items-center gap-2"><Sparkles size={20} className="text-blue-400"/> Pro</h3>
                            <div className="text-4xl font-extrabold text-white mb-1">$19<span className="text-lg font-normal text-slate-400">/mo</span></div>
                            <p className="text-sm text-blue-200">For serious builders.</p>
                        </div>
                        <ul className="space-y-4 mb-8 text-sm text-slate-200">
                            <li className="flex items-center gap-3"><Check size={16} className="text-blue-400"/> 500 Tokens instantly</li>
                            <li className="flex items-center gap-3"><Check size={16} className="text-blue-400"/> Gemini 1.5 Pro & Advanced</li>
                            <li className="flex items-center gap-3"><Check size={16} className="text-blue-400"/> Priority Execution Queue</li>
                            <li className="flex items-center gap-3"><Check size={16} className="text-blue-400"/> API Access</li>
                        </ul>
                        <button
                            onClick={handleUpgrade}
                            disabled={isUpgrading}
                            className="w-full py-3 rounded-xl bg-blue-500 hover:bg-blue-600 text-white font-bold transition-colors shadow-lg shadow-blue-500/30 flex items-center justify-center"
                        >
                            {isUpgrading ? 'Processing...' : 'Upgrade Now'}
                        </button>
                    </div>

                    {/* Enterprise Tier */}
                    <div className="bg-slate-900 rounded-3xl p-8 border border-slate-800 shadow-xl">
                        <div className="mb-6">
                            <h3 className="text-xl font-bold text-slate-300 mb-2 flex items-center gap-2"><Building2 size={20} className="text-slate-500"/> Enterprise</h3>
                            <div className="text-4xl font-extrabold mb-1">Custom</div>
                            <p className="text-sm text-slate-400">For massive scale.</p>
                        </div>
                        <ul className="space-y-4 mb-8 text-sm text-slate-300">
                            <li className="flex items-center gap-3"><Check size={16} className="text-blue-500"/> Unlimited Tokens</li>
                            <li className="flex items-center gap-3"><Check size={16} className="text-blue-500"/> Custom Agent SLAs</li>
                            <li className="flex items-center gap-3"><Check size={16} className="text-blue-500"/> Dedicated Account Manager</li>
                        </ul>
                        <button className="w-full py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-bold transition-colors border border-slate-700">
                            Contact Sales
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
