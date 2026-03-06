/**
 * DIAGNOSTICS TAB - System Diagnostics for Debugging Demucs Issues
 * 
 * Accessible via the System Info modal's "Run Diagnostics" button.
 * Provides comprehensive health checks and a live Demucs test.
 */
import { useState, useEffect } from 'react';
import axios from 'axios';
import { BACKEND_URL } from '../config';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Activity, Check, X, AlertTriangle, Loader2, Cpu, HardDrive,
    Package, Zap, Play, Copy, ChevronDown, ChevronRight, RefreshCw
} from 'lucide-react';

const StatusBadge = ({ status }) => {
    if (status === true || status === 'ok' || status === 'completed') {
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400"><Check className="w-3 h-3 mr-1" />OK</span>;
    }
    if (status === false || status === 'error' || status === 'failed') {
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-red-500/20 text-red-400"><X className="w-3 h-3 mr-1" />FAIL</span>;
    }
    if (status === 'warn' || status === 'warning') {
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-400"><AlertTriangle className="w-3 h-3 mr-1" />WARN</span>;
    }
    if (status === 'running') {
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-blue-500/20 text-blue-400"><Loader2 className="w-3 h-3 mr-1 animate-spin" />RUNNING</span>;
    }
    if (status === 'timeout') {
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-orange-500/20 text-orange-400"><AlertTriangle className="w-3 h-3 mr-1" />TIMEOUT</span>;
    }
    return <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-gray-500/20 text-gray-400">N/A</span>;
};

const CollapsibleSection = ({ title, icon: Icon, iconColor, children, defaultOpen = true, status }) => {
    const [isOpen, setIsOpen] = useState(defaultOpen);
    return (
        <div className="bg-dark-800/50 rounded-xl border border-white/5 overflow-hidden">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="w-full flex items-center justify-between p-4 hover:bg-white/5 transition-colors"
            >
                <div className="flex items-center space-x-3">
                    <Icon className={`w-5 h-5 ${iconColor}`} />
                    <h4 className="text-white font-bold text-sm">{title}</h4>
                    {status !== undefined && <StatusBadge status={status} />}
                </div>
                {isOpen ? <ChevronDown className="w-4 h-4 text-gray-500" /> : <ChevronRight className="w-4 h-4 text-gray-500" />}
            </button>
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden"
                    >
                        <div className="px-4 pb-4 pt-0">
                            {children}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

const InfoRow = ({ label, value, mono = false, status }) => (
    <div className="flex items-start justify-between py-1.5 border-b border-white/5 last:border-0">
        <span className="text-xs text-gray-500 flex-shrink-0 mr-4">{label}</span>
        <div className="flex items-center space-x-2">
            {status !== undefined && <StatusBadge status={status} />}
            <span className={`text-xs text-right ${mono ? 'font-mono text-gray-300' : 'text-white font-medium'} max-w-xs truncate`} title={typeof value === 'string' ? value : ''}>
                {value || 'N/A'}
            </span>
        </div>
    </div>
);


const DiagnosticsPanel = ({ onClose }) => {
    const [healthData, setHealthData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [testTaskId, setTestTaskId] = useState(null);
    const [testResult, setTestResult] = useState(null);
    const [testRunning, setTestRunning] = useState(false);
    const [copied, setCopied] = useState(false);
    const [showCpuWarning, setShowCpuWarning] = useState(false);

    const runHealthCheck = async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await axios.get(`${BACKEND_URL}/api/diagnostics/health`, { timeout: 60000 });
            setHealthData(response.data);

            // Auto-trigger CPU warning if detected
            if (response.data.cuda?.torch_version?.includes('+cpu')) {
                setShowCpuWarning(true);
            }
        } catch (err) {
            setError(err.response?.data?.detail || err.message || 'Failed to fetch diagnostics');
        } finally {
            setLoading(false);
        }
    };

    const runDemucsTest = async () => {
        setTestRunning(true);
        setTestResult(null);
        try {
            const response = await axios.post(`${BACKEND_URL}/api/diagnostics/test-demucs`);
            setTestTaskId(response.data.task_id);
        } catch (err) {
            setTestResult({ success: false, error: err.message });
            setTestRunning(false);
        }
    };

    // Poll test status
    useEffect(() => {
        if (!testTaskId) return;
        const interval = setInterval(async () => {
            try {
                const response = await axios.get(`${BACKEND_URL}/api/diagnostics/test-status/${testTaskId}`);
                const data = response.data;
                if (data.status === 'completed' || data.status === 'failed') {
                    setTestResult(data.result || { success: false, error: data.error });
                    setTestRunning(false);
                    setTestTaskId(null);
                    clearInterval(interval);
                }
            } catch (err) {
                // Keep polling
            }
        }, 1000);
        return () => clearInterval(interval);
    }, [testTaskId]);

    // Run health check on mount
    useEffect(() => {
        runHealthCheck();
    }, []);

    const copyReport = () => {
        if (!healthData) return;
        const d = healthData;
        let report = `## DemucsPleeter Diagnostics Report\n`;
        report += `Generated: ${new Date().toISOString()}\n\n`;

        report += `### System\n`;
        report += `- OS: ${d.system?.os} ${d.system?.os_release} (${d.system?.architecture})\n`;
        report += `- Python: ${d.system?.python_version?.split(' ')[0]}\n`;
        report += `- CPUs: ${d.system?.cpu_count}\n`;
        if (d.system?.ram_total_gb) report += `- RAM: ${d.system.ram_total_gb} GB total, ${d.system.ram_available_gb} GB free (${d.system.ram_percent_used}% used)\n`;
        report += `\n`;

        report += `### CUDA / GPU\n`;
        report += `- Available: ${d.cuda?.available ? 'YES ✓' : 'NO ✗'}\n`;
        report += `- PyTorch: ${d.cuda?.torch_version || 'N/A'}\n`;
        report += `- CUDA Version: ${d.cuda?.torch_cuda_version || 'N/A'}\n`;
        if (d.cuda?.devices) {
            d.cuda.devices.forEach(dev => {
                report += `- GPU ${dev.index}: ${dev.name} (${dev.total_memory_gb} GB VRAM)\n`;
            });
        }
        if (d.cuda?.hint) report += `- ⚠️ ${d.cuda.hint}\n`;
        if (d.cuda?.nvidia_smi_output) report += `- nvidia-smi: ${d.cuda.nvidia_smi_output}\n`;
        report += `\n`;

        report += `### FFmpeg\n`;
        report += `- Path: ${d.ffmpeg?.path || 'N/A'}\n`;
        report += `- Exists: ${d.ffmpeg?.exists ? 'YES' : 'NO'}\n`;
        report += `- Version: ${d.ffmpeg?.version || 'N/A'}\n`;
        report += `\n`;

        report += `### Packages\n`;
        if (d.packages) {
            Object.entries(d.packages).forEach(([pkg, ver]) => {
                report += `- ${pkg}: ${ver}\n`;
            });
        }
        report += `\n`;

        report += `### Demucs Import\n`;
        report += `- Importable: ${d.demucs_import?.importable ? 'YES' : 'NO'}\n`;
        report += `- separate module: ${d.demucs_import?.separate_importable ? 'YES' : 'NO'}\n`;
        if (d.demucs_import?.error) report += `- Error: ${d.demucs_import.error}\n`;
        report += `\n`;

        report += `### Disk Space\n`;
        if (d.disk) {
            Object.entries(d.disk).forEach(([name, info]) => {
                if (info.error) {
                    report += `- ${name}: ERROR - ${info.error}\n`;
                } else {
                    report += `- ${name}: ${info.free_gb} GB free / ${info.total_gb} GB total (${info.percent_used}% used)\n`;
                }
            });
        }
        report += `\n`;

        report += `### Model Files\n`;
        report += `- Pretrained dir: ${d.models?.pretrained_dir_exists ? 'EXISTS' : 'MISSING'} (${d.models?.total_files || 0} files)\n`;
        report += `- Torch hub cache: ${d.models?.torch_hub_exists ? 'EXISTS' : 'MISSING'}\n`;
        if (d.models?.hub_files?.length > 0) {
            d.models.hub_files.forEach(f => {
                report += `  - ${f.name} (${f.size_mb} MB)\n`;
            });
        }

        if (testResult) {
            report += `\n### Demucs Test\n`;
            report += `- Success: ${testResult.success ? 'YES ✓' : 'NO ✗'}\n`;
            if (testResult.elapsed_seconds) report += `- Time: ${testResult.elapsed_seconds}s\n`;
            if (testResult.device) report += `- Device: ${testResult.device}\n`;
            if (testResult.error) report += `- Error: ${testResult.error}\n`;
        }

        navigator.clipboard.writeText(report);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
            onClick={onClose}
        >
            <motion.div
                initial={{ scale: 0.9, y: 20 }}
                animate={{ scale: 1, y: 0 }}
                exit={{ scale: 0.9, y: 20 }}
                onClick={(e) => e.stopPropagation()}
                className="bg-dark-900/95 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl w-full max-w-3xl overflow-hidden"
                style={{ maxHeight: '85vh' }}
            >
                {/* Header */}
                <div className="flex items-center justify-between p-5 border-b border-white/10 bg-dark-800/50">
                    <div className="flex items-center space-x-3">
                        <div className="p-2 bg-amber-600/20 rounded-lg">
                            <Activity className="w-6 h-6 text-amber-400" />
                        </div>
                        <div>
                            <h3 className="text-lg font-bold text-white">System Diagnostics</h3>
                            <p className="text-xs text-gray-500">Debug Demucs, CUDA, FFmpeg, and system health</p>
                        </div>
                    </div>
                    <div className="flex items-center space-x-2">
                        <button
                            onClick={copyReport}
                            disabled={!healthData}
                            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center space-x-1.5 ${copied
                                ? 'bg-emerald-600/20 text-emerald-400'
                                : 'bg-dark-800 hover:bg-dark-700 text-gray-400 hover:text-white border border-white/10'
                                }`}
                            title="Copy full report to clipboard"
                        >
                            <Copy className="w-3.5 h-3.5" />
                            <span>{copied ? 'Copied!' : 'Copy Report'}</span>
                        </button>
                        <button
                            onClick={runHealthCheck}
                            disabled={loading}
                            className="px-3 py-1.5 bg-dark-800 hover:bg-dark-700 text-gray-400 hover:text-white rounded-lg text-xs font-bold transition-all flex items-center space-x-1.5 border border-white/10"
                        >
                            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                            <span>Refresh</span>
                        </button>
                        <button
                            onClick={onClose}
                            className="p-2 hover:bg-white/10 text-gray-400 hover:text-white rounded-lg transition-all"
                        >
                            <X className="w-5 h-5" />
                        </button>
                    </div>
                </div>

                {/* Content */}
                <div className="p-5 overflow-y-auto space-y-3" style={{ maxHeight: '70vh' }}>
                    {loading && !healthData && (
                        <div className="flex flex-col items-center justify-center py-16 space-y-3">
                            <div className="flex items-center">
                                <Loader2 className="w-8 h-8 text-amber-400 animate-spin" />
                                <span className="ml-3 text-gray-400">Running diagnostics...</span>
                            </div>
                            <p className="text-[10px] text-gray-600">CUDA and Demucs checks may take up to 20 seconds on slower machines</p>
                        </div>
                    )}

                    {error && (
                        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 flex items-start space-x-3">
                            <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                            <div>
                                <p className="text-red-300 font-medium text-sm">Diagnostics Failed</p>
                                <p className="text-red-400/70 text-xs mt-1">{error}</p>
                            </div>
                        </div>
                    )}

                    {healthData && (
                        <>
                            {/* CUDA / GPU - Most important for Demucs debugging */}
                            <CollapsibleSection
                                title="CUDA / GPU"
                                icon={Zap}
                                iconColor={healthData.cuda?.timed_out ? 'text-orange-400' : healthData.cuda?.available ? 'text-emerald-400' : 'text-red-400'}
                                status={healthData.cuda?.timed_out ? 'timeout' : healthData.cuda?.available}
                                defaultOpen={true}
                            >
                                <div className="space-y-0">
                                    {healthData.cuda?.timed_out && (
                                        <div className="mb-2 p-2 bg-orange-500/10 border border-orange-500/20 rounded-lg">
                                            <p className="text-xs text-orange-400"><AlertTriangle className="w-3 h-3 inline mr-1" />CUDA check timed out. PyTorch import is very slow on this machine. Try restarting the backend and running diagnostics again.</p>
                                        </div>
                                    )}
                                    <InfoRow label="CUDA Available" value={healthData.cuda?.timed_out ? 'Check timed out' : healthData.cuda?.available ? 'Yes ✓' : 'No ✗'} status={healthData.cuda?.timed_out ? 'timeout' : healthData.cuda?.available} />
                                    <InfoRow label="PyTorch Version" value={healthData.cuda?.torch_version} mono />
                                    <InfoRow label="CUDA Version" value={healthData.cuda?.torch_cuda_version || 'N/A'} mono />
                                    <InfoRow label="cuDNN Version" value={healthData.cuda?.cudnn_version || 'N/A'} mono />
                                    <InfoRow label="cuDNN Enabled" value={healthData.cuda?.cudnn_enabled ? 'Yes' : 'No'} />

                                    {healthData.cuda?.devices?.map(dev => (
                                        <div key={dev.index} className="mt-2 p-2 bg-dark-900/50 rounded-lg border border-white/5">
                                            <p className="text-xs text-emerald-400 font-bold mb-1">GPU {dev.index}: {dev.name}</p>
                                            <div className="grid grid-cols-3 gap-2 text-[10px] text-gray-400">
                                                <span>VRAM: <span className="text-white">{dev.total_memory_gb} GB</span></span>
                                                <span>Compute: <span className="text-white">{dev.major}.{dev.minor}</span></span>
                                                <span>SMs: <span className="text-white">{dev.multi_processor_count}</span></span>
                                            </div>
                                        </div>
                                    ))}

                                    {healthData.cuda?.memory_allocated_gb !== undefined && (
                                        <InfoRow label="Memory Allocated" value={`${healthData.cuda.memory_allocated_gb} GB`} mono />
                                    )}

                                    {healthData.cuda?.hint && (
                                        <div className="mt-2 p-2 bg-amber-500/10 border border-amber-500/20 rounded-lg">
                                            <p className="text-xs text-amber-400"><AlertTriangle className="w-3 h-3 inline mr-1" />{healthData.cuda.hint}</p>
                                        </div>
                                    )}

                                    {healthData.cuda?.nvidia_smi_output && (
                                        <InfoRow label="nvidia-smi" value={healthData.cuda.nvidia_smi_output} mono />
                                    )}

                                    {!healthData.cuda?.available && (
                                        <div className="mt-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg space-y-2">
                                            <div className="flex items-center justify-between">
                                                <p className="text-xs text-red-400 font-bold">⚠️ GPU Acceleration Disabled (CPU Mode)</p>
                                                <button
                                                    onClick={() => setShowCpuWarning(true)}
                                                    className="px-2 py-0.5 bg-red-500/20 hover:bg-red-500/30 text-red-400 text-[10px] font-bold rounded border border-red-500/30 transition-all underline decoration-red-500/30 underline-offset-2"
                                                >
                                                    View GPU Fix
                                                </button>
                                            </div>
                                            <p className="text-[10px] text-red-400/80 leading-relaxed">
                                                Demucs will run on your CPU, which is up to 50x slower than a GPU. If you have an NVIDIA card, you should install the CUDA version of PyTorch.
                                            </p>
                                        </div>
                                    )}
                                </div>
                            </CollapsibleSection>

                            {/* Demucs Import */}
                            <CollapsibleSection
                                title="Demucs Module"
                                icon={Activity}
                                iconColor={healthData.demucs_import?.timed_out ? 'text-orange-400' : healthData.demucs_import?.importable ? 'text-emerald-400' : 'text-red-400'}
                                status={healthData.demucs_import?.timed_out ? 'timeout' : healthData.demucs_import?.importable}
                            >
                                <InfoRow label="Importable" value={healthData.demucs_import?.importable ? 'Yes ✓' : 'No ✗'} status={healthData.demucs_import?.importable} />
                                <InfoRow label="demucs.separate" value={healthData.demucs_import?.separate_importable ? 'Yes ✓' : 'No ✗'} status={healthData.demucs_import?.separate_importable} />
                                {healthData.demucs_import?.location && (
                                    <InfoRow label="Location" value={healthData.demucs_import.location} mono />
                                )}
                                {healthData.demucs_import?.error && (
                                    <div className="mt-2 p-2 bg-red-500/10 border border-red-500/20 rounded-lg">
                                        <p className="text-xs text-red-400 font-mono break-all">{healthData.demucs_import.error}</p>
                                    </div>
                                )}
                                {healthData.demucs_import?.separate_error && (
                                    <div className="mt-2 p-2 bg-red-500/10 border border-red-500/20 rounded-lg">
                                        <p className="text-xs text-red-400 font-mono break-all">separate: {healthData.demucs_import.separate_error}</p>
                                    </div>
                                )}
                            </CollapsibleSection>

                            {/* Packages */}
                            <CollapsibleSection
                                title="Package Versions"
                                icon={Package}
                                iconColor="text-blue-400"
                                defaultOpen={false}
                            >
                                <div className="grid grid-cols-2 gap-x-6">
                                    {Object.entries(healthData.packages || {}).map(([pkg, ver]) => (
                                        <InfoRow
                                            key={pkg}
                                            label={pkg}
                                            value={ver}
                                            mono
                                            status={ver !== 'NOT INSTALLED' ? true : false}
                                        />
                                    ))}
                                </div>
                            </CollapsibleSection>

                            {/* System Info */}
                            <CollapsibleSection
                                title="System"
                                icon={Cpu}
                                iconColor="text-purple-400"
                                defaultOpen={false}
                            >
                                <InfoRow label="OS" value={`${healthData.system?.os} ${healthData.system?.os_release}`} />
                                <InfoRow label="Architecture" value={healthData.system?.architecture} />
                                <InfoRow label="Python" value={healthData.system?.python_version?.split(' ')[0]} mono />
                                <InfoRow label="CPU Cores" value={healthData.system?.cpu_count} />
                                {healthData.system?.ram_total_gb && (
                                    <>
                                        <InfoRow label="RAM Total" value={`${healthData.system.ram_total_gb} GB`} />
                                        <InfoRow label="RAM Available" value={`${healthData.system.ram_available_gb} GB`}
                                            status={healthData.system.ram_available_gb < 2 ? 'warn' : true}
                                        />
                                        <InfoRow label="RAM Used" value={`${healthData.system.ram_percent_used}%`}
                                            status={healthData.system.ram_percent_used > 90 ? 'warn' : true}
                                        />
                                    </>
                                )}
                                <InfoRow label="Working Dir" value={healthData.system?.cwd} mono />
                            </CollapsibleSection>

                            {/* FFmpeg */}
                            <CollapsibleSection
                                title="FFmpeg"
                                icon={Activity}
                                iconColor={healthData.ffmpeg?.exists ? 'text-emerald-400' : 'text-red-400'}
                                status={healthData.ffmpeg?.exists}
                                defaultOpen={false}
                            >
                                <InfoRow label="Path" value={healthData.ffmpeg?.path} mono />
                                <InfoRow label="Exists" value={healthData.ffmpeg?.exists ? 'Yes' : 'No'} status={healthData.ffmpeg?.exists} />
                                <InfoRow label="Version" value={healthData.ffmpeg?.version} mono />
                                {healthData.ffmpeg?.error && (
                                    <div className="mt-2 p-2 bg-red-500/10 border border-red-500/20 rounded-lg">
                                        <p className="text-xs text-red-400 font-mono">{healthData.ffmpeg.error}</p>
                                    </div>
                                )}
                            </CollapsibleSection>

                            {/* Disk Space */}
                            <CollapsibleSection
                                title="Disk Space"
                                icon={HardDrive}
                                iconColor="text-cyan-400"
                                defaultOpen={false}
                            >
                                {Object.entries(healthData.disk || {}).map(([name, info]) => (
                                    <div key={name} className="mb-2">
                                        <p className="text-xs text-gray-500 font-medium mb-1 capitalize">{name.replace(/_/g, ' ')}</p>
                                        {info.error ? (
                                            <p className="text-xs text-red-400">{info.error}</p>
                                        ) : (
                                            <div className="flex items-center space-x-3">
                                                <div className="flex-1 h-2 bg-dark-900 rounded-full overflow-hidden">
                                                    <div
                                                        className={`h-full rounded-full ${info.percent_used > 90 ? 'bg-red-500' :
                                                            info.percent_used > 75 ? 'bg-amber-500' : 'bg-emerald-500'
                                                            }`}
                                                        style={{ width: `${info.percent_used}%` }}
                                                    />
                                                </div>
                                                <span className="text-[10px] text-gray-400 font-mono flex-shrink-0">
                                                    {info.free_gb} GB free / {info.total_gb} GB
                                                </span>
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </CollapsibleSection>

                            {/* Model Files */}
                            <CollapsibleSection
                                title="Model Files"
                                icon={Package}
                                iconColor="text-orange-400"
                                defaultOpen={false}
                                status={healthData.models?.pretrained_dir_exists}
                            >
                                <InfoRow label="Pretrained Dir" value={healthData.models?.pretrained_dir_exists ? 'Exists' : 'Missing'} status={healthData.models?.pretrained_dir_exists} />
                                <InfoRow label="Files in pretrained/" value={healthData.models?.total_files || 0} />
                                <InfoRow label="Torch Hub Cache" value={healthData.models?.torch_hub_exists ? 'Exists' : 'Missing'} status={healthData.models?.torch_hub_exists ? true : 'warn'} />

                                {healthData.models?.hub_files?.length > 0 && (
                                    <div className="mt-2 space-y-1">
                                        <p className="text-[10px] text-gray-500 font-bold uppercase">Cached Models:</p>
                                        {healthData.models.hub_files.map((f, i) => (
                                            <div key={i} className="flex justify-between text-[10px] text-gray-400 py-0.5">
                                                <span className="font-mono truncate mr-2">{f.name}</span>
                                                <span className="text-gray-500 flex-shrink-0">{f.size_mb} MB</span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </CollapsibleSection>

                            {/* LIVE DEMUCS TEST */}
                            <div className="bg-gradient-to-br from-amber-900/20 to-orange-900/20 rounded-xl border border-amber-500/20 p-5">
                                <div className="flex items-center justify-between mb-3">
                                    <div className="flex items-center space-x-3">
                                        <div className="p-2 bg-amber-600/20 rounded-lg">
                                            <Play className="w-5 h-5 text-amber-400" />
                                        </div>
                                        <div>
                                            <h4 className="text-white font-bold text-sm">Live Demucs Test</h4>
                                            <p className="text-[10px] text-gray-500">Generates a 5-second tone and runs Demucs separation</p>
                                        </div>
                                    </div>
                                    <button
                                        onClick={runDemucsTest}
                                        disabled={testRunning}
                                        className={`px-4 py-2 rounded-lg text-xs font-bold transition-all flex items-center space-x-2 ${testRunning
                                            ? 'bg-amber-900/30 text-amber-400/50 cursor-not-allowed'
                                            : 'bg-amber-600/20 hover:bg-amber-600/30 text-amber-400 border border-amber-500/30 hover:border-amber-500/50'
                                            }`}
                                    >
                                        {testRunning ? (
                                            <>
                                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                                <span>Running...</span>
                                            </>
                                        ) : (
                                            <>
                                                <Play className="w-3.5 h-3.5" />
                                                <span>Run Test</span>
                                            </>
                                        )}
                                    </button>
                                </div>

                                {testResult && (
                                    <motion.div
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        className={`mt-3 p-3 rounded-lg border ${testResult.success
                                            ? 'bg-emerald-500/10 border-emerald-500/20'
                                            : 'bg-red-500/10 border-red-500/20'
                                            }`}
                                    >
                                        <div className="flex items-center space-x-2 mb-2">
                                            <StatusBadge status={testResult.success ? 'completed' : 'failed'} />
                                            <span className={`text-sm font-bold ${testResult.success ? 'text-emerald-400' : 'text-red-400'}`}>
                                                {testResult.success ? 'Demucs is working!' : 'Demucs test failed'}
                                            </span>
                                        </div>

                                        {testResult.elapsed_seconds && (
                                            <p className="text-xs text-gray-400">
                                                Processing time: <span className="text-white font-mono">{testResult.elapsed_seconds}s</span>
                                                {testResult.device && <> on <span className="text-blue-400">{testResult.device}</span></>}
                                            </p>
                                        )}

                                        {testResult.stems_found && (
                                            <div className="mt-2 grid grid-cols-4 gap-2">
                                                {Object.entries(testResult.stems_found).map(([stem, info]) => (
                                                    <div key={stem} className={`text-[10px] p-1.5 rounded text-center ${info.exists
                                                        ? 'bg-emerald-500/10 text-emerald-400'
                                                        : 'bg-red-500/10 text-red-400'
                                                        }`}>
                                                        {info.exists ? '✓' : '✗'} {stem}
                                                        {info.size_kb && <span className="block text-gray-500">{info.size_kb} KB</span>}
                                                    </div>
                                                ))}
                                            </div>
                                        )}

                                        {testResult.error && typeof testResult.error === 'string' && (
                                            <div className="mt-2 p-2 bg-dark-900/50 rounded text-[10px] text-red-400 font-mono max-h-32 overflow-y-auto whitespace-pre-wrap break-all">
                                                {testResult.error}
                                            </div>
                                        )}
                                    </motion.div>
                                )}
                            </div>
                        </>
                    )}
                </div>
            </motion.div>

            {/* GPU Fix Modal Overlay */}
            <AnimatePresence>
                {showCpuWarning && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-[70] flex items-center justify-center p-6 bg-black/80 backdrop-blur-md"
                        onClick={() => setShowCpuWarning(false)}
                    >
                        <motion.div
                            initial={{ scale: 0.9, y: 20 }}
                            animate={{ scale: 1, y: 0 }}
                            exit={{ scale: 0.9, y: 20 }}
                            onClick={(e) => e.stopPropagation()}
                            className="bg-dark-900 border border-red-500/30 rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden"
                        >
                            <div className="p-6 border-b border-white/5 bg-red-500/10 flex items-center justify-between">
                                <div className="flex items-center space-x-3">
                                    <div className="p-2 bg-red-500/20 rounded-lg">
                                        <AlertTriangle className="w-6 h-6 text-red-400" />
                                    </div>
                                    <h3 className="text-lg font-bold text-white">GPU Acceleration Fix</h3>
                                </div>
                                <button onClick={() => setShowCpuWarning(false)} className="p-2 hover:bg-white/10 rounded-lg text-gray-400 hover:text-white transition-all">
                                    <X className="w-5 h-5" />
                                </button>
                            </div>

                            <div className="p-6 space-y-4">
                                <p className="text-sm text-gray-300">
                                    We detected that <span className="text-red-400 font-bold">PyTorch (CPU version)</span> is installed.
                                    This makes audio separation extremely slow.
                                </p>

                                <div className="space-y-4">
                                    <div className="space-y-2">
                                        <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Step 1: Uninstall CPU version</p>
                                        <div className="bg-black/40 rounded-lg p-3 border border-white/5 relative group">
                                            <code className="text-xs text-blue-400 font-mono block break-all">
                                                uv pip uninstall torch torchvision torchaudio
                                            </code>
                                            <button
                                                onClick={() => navigator.clipboard.writeText("uv pip uninstall torch torchvision torchaudio")}
                                                className="absolute top-2 right-2 p-1.5 bg-dark-800 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                                            >
                                                <Copy className="w-3.5 h-3.5 text-gray-400" />
                                            </button>
                                        </div>
                                    </div>

                                    <div className="space-y-2">
                                        <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Step 2: Install GPU version (CUDA 12.8)</p>
                                        <div className="bg-black/40 rounded-lg p-3 border border-white/5 relative group font-mono">
                                            <code className="text-xs text-emerald-400 block break-all">
                                                uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
                                            </code>
                                            <button
                                                onClick={() => navigator.clipboard.writeText("uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128")}
                                                className="absolute top-2 right-2 p-1.5 bg-dark-800 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                                            >
                                                <Copy className="w-3.5 h-3.5 text-gray-400" />
                                            </button>
                                        </div>
                                        <p className="text-[10px] text-gray-500 italic">Note: Replace <span className="text-white">cu128</span> with your specific CUDA version if different (e.g., cu118, cu121).</p>
                                    </div>
                                </div>

                                <div className="pt-4 flex justify-end">
                                    <button
                                        onClick={() => setShowCpuWarning(false)}
                                        className="px-6 py-2 bg-dark-800 hover:bg-dark-700 text-white rounded-xl text-sm font-bold transition-all border border-white/10"
                                    >
                                        Dismiss
                                    </button>
                                </div>
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
};

export default DiagnosticsPanel;
