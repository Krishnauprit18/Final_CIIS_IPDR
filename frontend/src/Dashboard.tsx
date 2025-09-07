import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import Graph from 'react-graph-vis';
import { 
    Typography, Box, Button, Paper, 
    CircularProgress, Alert, TextField, Card, CardContent,
    Chip, Badge, List, ListItemText, ListItemIcon,
    Table, TableBody, TableCell, TableContainer,
    TableHead, TableRow, LinearProgress, Divider,
    Drawer, ListSubheader, ListItemButton, Avatar,
    ListItem, Select, MenuItem, FormControl, InputLabel, Collapse
} from '@mui/material';
import { 
    Phone, Wifi, Warning, Search, Timeline,
    AccessTime, Security, UploadFile,
    AccountCircle, Edit, Save, LockReset, Cancel,
    ExpandMore, ExpandLess
} from '@mui/icons-material';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { ChipProps } from '@mui/material/Chip'; // Import ChipProps for type safety

// --- FIX 1: Debounce function implementation ---
// The 'debounce' function was used but not defined. 
// This is a standard utility function to delay execution of a function until after a certain time has passed.
const debounce = <F extends (...args: any[]) => any>(func: F, waitFor: number) => {
    let timeout: NodeJS.Timeout;

    return (...args: Parameters<F>): Promise<ReturnType<F>> =>
        new Promise(resolve => {
            if (timeout) {
                clearTimeout(timeout);
            }

            timeout = setTimeout(() => resolve(func(...args)), waitFor);
        });
};


const API_URL = 'http://localhost:8000';

// Type for the graph data
interface GraphData {
    nodes: { id: string; label: string }[];
    edges: { from: string; to: string }[];
}

// Dashboard data interfaces
interface DashboardStats {
    total_records: number;
    unique_phones: number;
    unique_ips: number;
    suspicious_activities: number;
    time_range: string;
}

interface SuspiciousActivity {
    id: string;
    type: string;
    severity: string;
    description: string;
    timestamp: string;
    phone?: string;
    ip?: string;
    data?: any;
}

interface ExtractedNumber {
    phone: string;
    customer_name: string;
    subscriber_id: string;
    total_calls: number;
    risk_level: string;
}

interface CallRelationship {
    source: string;
    destination: string;
    call_count: number;
    total_duration: number;
    relationship_strength: number;
}

interface UserProfile {
    username: string;
    email?: string | null;
    role?: string;
    name?: string | null;
    post?: string | null;
    district?: string | null;
    thana?: string | null;
    created_at?: string | null;
}

const Dashboard: React.FC = () => {
    // File and upload state
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [uploadResponse, setUploadResponse] = useState<{ message: string; records_found: number } | null>(null);

    // Data and graph state
    const [rows, setRows] = useState<any[]>([]);
    const [columns, setColumns] = useState<GridColDef[]>([]);
    const [graphData, setGraphData] = useState<GraphData>({ nodes: [], edges: [] });
    const [loadingData, setLoadingData] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');

    // Dashboard-specific state
    const [activeTab, setActiveTab] = useState(0);
    const [dashboardStats, setDashboardStats] = useState<DashboardStats | null>(null);
    const [suspiciousActivities, setSuspiciousActivities] = useState<SuspiciousActivity[]>([]);
    const [expandedAlerts, setExpandedAlerts] = useState<Set<string>>(new Set());
    const [extractedNumbers, setExtractedNumbers] = useState<ExtractedNumber[]>([]);
    const [callRelationships, setCallRelationships] = useState<CallRelationship[]>([]);
    const [, setLoadingStats] = useState(false);
    const [phoneSearchQuery, setPhoneSearchQuery] = useState('');
    const [ipSearchQuery, setIpSearchQuery] = useState('');
    // B-Party & Filters/Normalization
    const [bpartyIPs, setBpartyIPs] = useState<any[]>([]);
    const [bpartyPhones, setBpartyPhones] = useState<any[]>([]);
    const [normalizationStats, setNormalizationStats] = useState<any | null>(null);
    const [filterStats, setFilterStats] = useState<any | null>(null);
    // Cases
    const [cases, setCases] = useState<any[]>([]);
    const [newCaseName, setNewCaseName] = useState('');
    const [selectedCaseId, setSelectedCaseId] = useState<number | ''>('');
    const [savedSearches, setSavedSearches] = useState<any[]>([]);
    const [saveNotes, setSaveNotes] = useState('');
    const [lastSearchCriteria, setLastSearchCriteria] = useState<any | null>(null);
    // Enrichment
    const [ipLookup, setIpLookup] = useState('');
    const [ipEnrichment, setIpEnrichment] = useState<any | null>(null);
    // Correlation (A->B)
    const [corrNodes, setCorrNodes] = useState<{id:string,label:string}[]>([]);
    const [corrEdges, setCorrEdges] = useState<{from:string,to:string,value?:number}[]>([]);
    const [corrTopPairs, setCorrTopPairs] = useState<any[]>([]);
    // Geo Maps (iframes to backend HTML)
    const [suspMapSrc, setSuspMapSrc] = useState<string>('');
    const [convMapSrc, setConvMapSrc] = useState<string>('');
    const [convA, setConvA] = useState<string>('');
    const [convB, setConvB] = useState<string>('');
    // Link Analysis removed (map rendered within Suspicious Phones section)
    
    // Profile state
    const [profile, setProfile] = useState<UserProfile | null>(null);
    const [profileEdit, setProfileEdit] = useState(false);
    const [profileForm, setProfileForm] = useState<Partial<UserProfile>>({});
    const [pwFormOpen, setPwFormOpen] = useState(false);
    const [pwCurrent, setPwCurrent] = useState('');
    const [pwNew, setPwNew] = useState('');
    const [pwConfirm, setPwConfirm] = useState('');
    const [profileMsg, setProfileMsg] = useState<string | null>(null);
    const [profileErr, setProfileErr] = useState<string | null>(null);

    // --- FIX 2: Correctly define fetchData as a useCallback to stabilize its identity ---
    // This avoids re-creating the function on every render, which is important when it's a dependency of other hooks.
    const fetchData = useCallback(async (query: string) => {
        setLoadingData(true);
        try {
            const response = await axios.get(`${API_URL}/data`, { params: { query } });
            if (response.data && response.data.length > 0) {
                const firstItem = response.data[0];
                const generatedColumns: GridColDef[] = Object.keys(firstItem).map((key) => ({
                    field: key,
                    headerName: key.replace(/_/g, ' ').toUpperCase(),
                    width: 150,
                }));
                setColumns(generatedColumns);
                setRows(response.data.map((row: any, index: number) => ({ id: index, ...row })));
            } else {
                setRows([]);
                setColumns([]); // Also clear columns if no data
            }
        } catch (err) {
            setError('Could not fetch data from the backend.');
        }
        setLoadingData(false);
    }, []);

    const fetchGraphData = useCallback(async (limit: number = 50) => {
        try {
            const response = await axios.get(`${API_URL}/graph?limit=${limit}`);
            setGraphData(response.data);
        } catch (err) {
            setError('Could not fetch graph data from the backend.');
        }
    }, []);
    
    // Fetch profile
    const fetchProfile = useCallback(async () => {
        try {
            const res = await axios.get(`${API_URL}/auth/me`);
            setProfile(res.data);
            setProfileForm({
                name: res.data.name ?? '',
                post: res.data.post ?? '',
                district: res.data.district ?? '',
                thana: res.data.thana ?? '',
            });
        } catch (e: any) {
            // Ignore if unauthorized
        }
    }, []);

    useEffect(() => {
        fetchProfile();
    }, [fetchProfile]);

    const saveProfile = async () => {
        try {
            setProfileErr(null);
            setProfileMsg(null);
            await axios.put(`${API_URL}/auth/profile`, {
                name: profileForm.name,
                post: profileForm.post,
                district: profileForm.district,
                thana: profileForm.thana,
            });
            setProfileEdit(false);
            setProfileMsg('Profile saved');
            fetchProfile();
        } catch (e: any) {
            setProfileErr(e?.response?.data?.detail || e?.message || 'Failed to save profile');
        }
    };

    const changePassword = async () => {
        if (pwNew.length < 6) {
            setProfileErr('New password must be at least 6 characters');
            return;
        }
        if (pwNew !== pwConfirm) {
            setProfileErr('New passwords do not match');
            return;
        }
        try {
            setProfileErr(null);
            const res = await axios.post(`${API_URL}/auth/change-password`, {
                current_password: pwCurrent,
                new_password: pwNew,
            });
            setProfileMsg(res.data?.message || 'Password changed.');
            setPwCurrent('');
            setPwNew('');
            setPwConfirm('');
            setPwFormOpen(false);
        } catch (e: any) {
            setProfileErr(e?.response?.data?.detail || 'Failed to change password');
        }
    };

    const drawerWidth = 220;

    // Fetch dashboard statistics
    const fetchDashboardStats = useCallback(async () => {
        setLoadingStats(true);
        try {
            const response = await axios.get(`${API_URL}/search/statistics`);
            const searchStats = response.data.search_statistics;
            
            setDashboardStats({
                total_records: searchStats.total_records || 0,
                unique_phones: searchStats.unique_counts?.Phone || 0,
                unique_ips: (searchStats.unique_counts?.['Source IP'] || 0) + (searchStats.unique_counts?.['Destination IP'] || 0),
                suspicious_activities: 0,
                time_range: `${searchStats.date_range?.start?.split('T')[0] || 'N/A'} to ${searchStats.date_range?.end?.split('T')[0] || 'N/A'}`
            });
        } catch (err) {
            setError('Could not fetch dashboard statistics.');
        } finally {
            setLoadingStats(false);
        }
    }, []);

    // Fetch suspicious activities
    const fetchSuspiciousActivities = useCallback(async () => {
        try {
            const response = await axios.get(`${API_URL}/suspicious/comprehensive-analysis`);
            const activities: SuspiciousActivity[] = [];
            
            if (response.data.suspicious_activities) {
                Object.entries(response.data.suspicious_activities).forEach(([type, data]: [string, any]) => {
                    if (Array.isArray(data)) {
                        data.slice(0, 10).forEach((item: any, index: number) => {
                            activities.push({
                                id: `${type}_${index}`,
                                type: type.replace(/_/g, ' ').toUpperCase(),
                                severity: item.severity || 'MEDIUM',
                                description: item.description || `${type.replace(/_/g, ' ')} detected`,
                                timestamp: item.timestamp || new Date().toISOString(),
                                phone: item.phone,
                                ip: item.source_ip || item.destination_ip,
                                data: item
                            });
                        });
                    }
                });
            }

            setSuspiciousActivities(activities);
            setDashboardStats(prev => prev ? { ...prev, suspicious_activities: activities.length } : null);
        } catch (err) {
            setError('Could not fetch suspicious activities.');
        }
    }, []);

    const toggleAlertExpand = (id: string) => {
        setExpandedAlerts(prev => {
            const next = new Set(Array.from(prev));
            if (next.has(id)) next.delete(id); else next.add(id);
            return next;
        });
    };

    const detailRowsForAlert = (a: SuspiciousActivity) => {
        const d: any = a.data || {};
        const pick = (...keys: string[]) => {
            for (const k of keys) { if (d[k] !== undefined && d[k] !== null && String(d[k]).trim() !== '') return d[k]; }
            return undefined;
        };
        const rows: {label: string; value: any}[] = [];
        const sub = pick('subscriber_id','SubscriberID');
        if (sub) rows.push({ label: 'Subscriber ID', value: sub });
        const name = pick('customer_name','Customer_Name','CustName','customer');
        if (name) rows.push({ label: 'Customer Name', value: name });
        const ph = a.phone || pick('phone','Phone');
        if (ph) rows.push({ label: 'Phone', value: ph });
        const email = pick('email','Email');
        if (email) rows.push({ label: 'Email', value: email });
        const addr = pick('address','Address');
        if (addr) rows.push({ label: 'Address', value: addr });
        const sip = a.ip || pick('source_ip','Source_IP');
        if (sip) rows.push({ label: 'Source IP', value: sip });
        const dip = pick('destination_ip','Destination_IP');
        if (dip) rows.push({ label: 'Destination IP', value: dip });
        const proto = pick('protocol','Protocol','protocols');
        if (proto) rows.push({ label: 'Protocol(s)', value: Array.isArray(proto) ? proto.join(', ') : proto });
        const dur = pick('duration','avg_duration','Total_Duration');
        if (dur !== undefined) rows.push({ label: 'Duration', value: dur });
        const uniq = pick('unique_destinations','Unique_Destinations');
        if (uniq) rows.push({ label: 'Unique Destinations', value: uniq });
        const risk = pick('risk_score','suspicion_score');
        if (risk !== undefined) rows.push({ label: 'Risk/Suspicion Score', value: risk });
        return rows;
    };

    // Fetch extracted numbers (phone analysis)
    const fetchExtractedNumbers = useCallback(async () => {
        try {
            const response = await axios.get(`${API_URL}/mapping/phone-connections`);
            const phoneData = response.data.phone_connections || [];
            
            const extractedNums: ExtractedNumber[] = phoneData.slice(0, 20).map((item: any) => ({
                phone: item.Phone || 'Unknown',
                customer_name: item.Customer_Name || 'Unknown',
                subscriber_id: item.Subscriber_ID || 'Unknown',
                total_calls: item.Connections || 0,
                risk_level: 'LOW' // Placeholder
            }));

            setExtractedNumbers(extractedNums);
        } catch (err) {
            setError('Could not fetch extracted numbers.');
        }
    }, []);

    // Fetch call relationships
    const fetchCallRelationships = useCallback(async () => {
        try {
            const response = await axios.get(`${API_URL}/mapping/ip-connections`);
            const relationshipData = response.data.ip_connections || [];
            
            const relationships: CallRelationship[] = relationshipData.slice(0, 15).map((item: any) => ({
                source: item.Source_IP || 'Unknown',
                destination: item.Destination_IP || 'Unknown',
                call_count: item.Communication_Count || 0,
                total_duration: item.Total_Duration || 0,
                relationship_strength: item.Communication_Count || 0
            }));

            setCallRelationships(relationships);
        } catch (err) {
            setError('Could not fetch call relationships.');
        }
    }, []);

    // B-Party summary fetch
    const fetchBpartySummary = useCallback(async () => {
        try {
            const res = await axios.get(`${API_URL}/relationships/bparty-summary`);
            const ips = Object.entries(res.data.b_party_ip_summary || {}).map(([ip, v]: any) => ({
                ip,
                total: v.total_connections,
                unique_sources: v.unique_source_count,
                ip_category: v.ip_category,
                is_public: v.is_public,
                top_ports: (v.top_ports || []).map((p: any) => p[0]).join(', ')
            }));
            const phones = Object.entries(res.data.b_party_phone_summary || {}).map(([phone, v]: any) => ({
                phone,
                total: v.total_connections,
                unique_sources: v.unique_source_count,
            }));
            setBpartyIPs(ips.slice(0, 50));
            setBpartyPhones(phones.slice(0, 50));
        } catch (e) {
            // ignore silently for demo
        }
    }, []);

    // Normalization stats
    const fetchNormalizationStats = useCallback(async () => {
        try {
            const res = await axios.get(`${API_URL}/normalization/stats`);
            setNormalizationStats(res.data?.normalization_statistics || null);
        } catch (e) { /* ignore */ }
    }, []);

    // Investigation filters
    const runInvestigationFilters = useCallback(async () => {
        try {
            const res = await axios.get(`${API_URL}/filters/investigation-focus`);
            setFilterStats(res.data?.filter_statistics || res.data?.filter_stats || null);
        } catch (e) { setFilterStats(null); }
    }, []);

    // Cases helpers
    const fetchCases = useCallback(async () => {
        try {
            const res = await axios.get(`${API_URL}/cases`);
            setCases(res.data?.cases || []);
        } catch (e) { /* ignore */ }
    }, []);
    const createCase = async () => {
        if (!newCaseName.trim()) return;
        try {
            await axios.post(`${API_URL}/cases`, { name: newCaseName.trim() });
            setNewCaseName('');
            fetchCases();
        } catch (e) { /* ignore */ }
    };
    const loadSavedSearches = useCallback(async (caseId: number) => {
        try {
            const res = await axios.get(`${API_URL}/cases/${caseId}/searches`);
            setSavedSearches(res.data?.saved_searches || []);
        } catch (e) { setSavedSearches([]); }
    }, []);
    const saveCurrentSearchToCase = async () => {
        if (!selectedCaseId || !lastSearchCriteria) return;
        try {
            await axios.post(`${API_URL}/cases/${selectedCaseId}/save-search`, {
                criteria_json: lastSearchCriteria,
                notes: saveNotes,
            });
            setSaveNotes('');
            loadSavedSearches(selectedCaseId as number);
        } catch (e) { /* ignore */ }
    };
    const exportCasePack = async () => {
        if (!selectedCaseId) return;
        try {
            const res = await axios.post(`${API_URL}/cases/${selectedCaseId}/export-pack`);
            alert(`Exported: ${res.data?.export_file}`);
        } catch (e) { /* ignore */ }
    };

    // Enrichment
    const enrichIp = async (ip: string) => {
        if (!ip) return;
        try {
            const res = await axios.get(`${API_URL}/enrich/ip`, { params: { ip } });
            setIpEnrichment(res.data?.enrichment || null);
        } catch (e) { setIpEnrichment(null); }
    };

    // Fetch A->B correlation
    const fetchCorrelation = useCallback(async (limit: number = 100) => {
        try {
            const res = await axios.get(`${API_URL}/correlation/a2b?limit=${limit}`);
            const n = (res.data?.nodes || []).map((x:any)=>({ id: x.id, label: x.label }));
            const e = (res.data?.edges || []).map((x:any)=>({ from: x.from, to: x.to, value: x.value }));
            setCorrNodes(n); setCorrEdges(e); setCorrTopPairs(res.data?.top_pairs || []);
        } catch (e) {
            setCorrNodes([]); setCorrEdges([]); setCorrTopPairs([]);
        }
    }, []);

    const handleProcessData = async () => {
        setUploading(true);
        setError(null);
        setUploadResponse(null);
        try {
            const response = await axios.post(`${API_URL}/process-data`);
            setUploadResponse(response.data);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'An unexpected error occurred during processing.');
        }
        setUploading(false);
    };

    const handleSearch = async (type: 'phone' | 'ip') => {
        const query = type === 'phone' ? phoneSearchQuery : ipSearchQuery;
        if (!query) return;

        setLoadingData(true);
        try {
            const response = await axios.get(`${API_URL}/search/${type}/${query}`);
            const records = response.data.records || [];
            const searchResults = records.map((row: any, index: number) => ({ id: index, ...row }));
            setRows(searchResults);
            setLastSearchCriteria({ type, query });
            
            if (searchResults.length > 0) {
                const firstItem = searchResults[0];
                const generatedColumns: GridColDef[] = Object.keys(firstItem)
                    .map((key) => ({
                        field: key,
                        headerName: key.replace(/_/g, ' ').toUpperCase(),
                        width: 150,
                    }));
                setColumns(generatedColumns);
            } else {
                setColumns([]);
            }
        } catch (err) {
            setError(`${type.toUpperCase()} search failed`);
        }
        setLoadingData(false);
    };
    
    // Fetch data after a successful upload
    useEffect(() => {
        if (uploadResponse && uploadResponse.records_found > 0) {
            fetchData('');
            fetchGraphData();
            fetchDashboardStats();
            fetchSuspiciousActivities();
            fetchExtractedNumbers();
            fetchCallRelationships();
            fetchBpartySummary();
            fetchNormalizationStats();
            fetchCases();
        }
    }, [uploadResponse, fetchData, fetchGraphData, fetchDashboardStats, fetchSuspiciousActivities, fetchExtractedNumbers, fetchCallRelationships, fetchBpartySummary, fetchNormalizationStats, fetchCases]);

    // Debounced search handler for the raw data tab
    // eslint-disable-next-line react-hooks/exhaustive-deps
    const debouncedSearch = useCallback(debounce((query: string) => fetchData(query), 500), [fetchData]);

    const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setSearchQuery(event.target.value);
        debouncedSearch(event.target.value);
    };

    // --- FIX 3: Type-safe color utility for Chip components ---
    // The `color` prop for Chip does not accept 'inherit'. This function now returns a valid Chip color.
    const getSeverityColorForChip = (severity: string): ChipProps['color'] => {
        switch (severity.toLowerCase()) {
            case 'high': return 'error';
            case 'medium': return 'warning';
            case 'low': return 'info';
            default: return 'default';
        }
    };

    const getSeverityColorForIcon = (severity: string) => {
        switch (severity.toLowerCase()) {
            case 'high': return 'error';
            case 'medium': return 'warning';
            case 'low': return 'info';
            default: return 'inherit';
        }
    };

    const getRiskColor = (risk: string) => {
        switch (risk.toLowerCase()) {
            case 'high': return '#f44336';
            case 'medium': return '#ff9800';
            case 'low': return '#4caf50';
            default: return '#9e9e9e';
        }
    };

    return (
        <Box sx={{ display: 'flex' }}>
            {/* Left navigation drawer */}
            <Drawer
                variant="permanent"
                sx={{
                    width: drawerWidth,
                    flexShrink: 0,
                    '& .MuiDrawer-paper': { width: drawerWidth, boxSizing: 'border-box', p: 1.5 },
                }}
            >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                    <Avatar><AccountCircle /></Avatar>
                    <Box>
                        <Typography variant="subtitle1">{profile?.name || profile?.username || 'User'}</Typography>
                        <Typography variant="caption" color="text.secondary">{profile?.role || ''}</Typography>
                    </Box>
                </Box>

                <List subheader={<ListSubheader disableSticky>Features</ListSubheader>}>
                    <ListItemButton selected={activeTab===0} onClick={() => setActiveTab(0)}>
                        <ListItemIcon><Phone /></ListItemIcon>
                        <ListItemText primary="Extracted Numbers" />
                    </ListItemButton>
                    <ListItemButton selected={activeTab===1} onClick={() => setActiveTab(1)}>
                        <ListItemIcon><Timeline /></ListItemIcon>
                        <ListItemText primary="Call Relationships" />
                    </ListItemButton>
                    <ListItemButton selected={activeTab===2} onClick={() => setActiveTab(2)}>
                        <ListItemIcon><Warning /></ListItemIcon>
                        <ListItemText primary="Red Flags & Alerts" />
                    </ListItemButton>
                    <ListItemButton selected={activeTab===3} onClick={() => setActiveTab(3)}>
                        <ListItemIcon><Search /></ListItemIcon>
                        <ListItemText primary="Search & Analysis" />
                    </ListItemButton>
                    <ListItemButton selected={activeTab===4} onClick={() => setActiveTab(4)}>
                        <ListItemIcon><Wifi /></ListItemIcon>
                        <ListItemText primary="Network Graph" />
                    </ListItemButton>
                    <ListItemButton selected={activeTab===5} onClick={() => setActiveTab(5)}>
                        <ListItemIcon><Wifi /></ListItemIcon>
                        <ListItemText primary="Raw Data" />
                    </ListItemButton>
                    <ListItemButton selected={activeTab===6} onClick={() => setActiveTab(6)}>
                        <ListItemIcon><Phone /></ListItemIcon>
                        <ListItemText primary="B‑Party Summary" />
                    </ListItemButton>
                    <ListItemButton selected={activeTab===7} onClick={() => { setActiveTab(7); }}>
                        <ListItemIcon><Search /></ListItemIcon>
                        <ListItemText primary="Normalization & Filters" />
                    </ListItemButton>
                    <ListItemButton selected={activeTab===8} onClick={() => { setActiveTab(8); if (selectedCaseId) loadSavedSearches(selectedCaseId as number); }}>
                        <ListItemIcon><AccountCircle /></ListItemIcon>
                        <ListItemText primary="Cases" />
                    </ListItemButton>
                    <ListItemButton selected={activeTab===9} onClick={() => setActiveTab(9)}>
                        <ListItemIcon><Wifi /></ListItemIcon>
                        <ListItemText primary="Enrichment" />
                    </ListItemButton>
                    <ListItemButton selected={activeTab===10} onClick={() => { setActiveTab(10); fetchCorrelation(100); }}>
                        <ListItemIcon><Timeline /></ListItemIcon>
                        <ListItemText primary="Correlation (A→B)" />
                    </ListItemButton>
                    <ListItemButton selected={activeTab===11} onClick={() => { setActiveTab(11); setSuspMapSrc(`${API_URL}/map/suspicious-phones/html?days=7`); }}>
                        <ListItemIcon><Wifi /></ListItemIcon>
                        <ListItemText primary="Geo Map" />
                    </ListItemButton>
                </List>

                <Divider sx={{ my: 1 }} />
                <Typography variant="subtitle2" sx={{ mb: 1 }}>Your Profile</Typography>
                <Box>
                    {profileErr && <Alert severity="error" sx={{ mb: 1 }}>{profileErr}</Alert>}
                    {profileMsg && <Alert severity="success" sx={{ mb: 1 }}>{profileMsg}</Alert>}
                    {profile && !profileEdit && (
                        <Box>
                            <Typography variant="body2"><strong>Name:</strong> {profile.name || '-'}</Typography>
                            <Typography variant="body2"><strong>Username:</strong> {profile.username}</Typography>
                            {profile.email && (<Typography variant="body2"><strong>Email:</strong> {profile.email}</Typography>)}
                            {profile.post && (<Typography variant="body2"><strong>Post:</strong> {profile.post}</Typography>)}
                            {profile.district && (<Typography variant="body2"><strong>District:</strong> {profile.district}</Typography>)}
                            {profile.thana && (<Typography variant="body2"><strong>Thana:</strong> {profile.thana}</Typography>)}
                            <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
                                <Button size="small" startIcon={<Edit />} onClick={() => { setProfileEdit(true); setProfileMsg(null); }}>
                                    Edit
                                </Button>
                                <Button size="small" startIcon={<LockReset />} onClick={() => { setPwFormOpen((v) => !v); setProfileErr(null); setProfileMsg(null);} }>
                                    {pwFormOpen ? 'Cancel' : 'Change Password'}
                                </Button>
                            </Box>
                        </Box>
                    )}
                    {profileEdit && (
                        <Box>
                            <TextField size="small" fullWidth label="Name" value={(profileForm.name as string) || ''} onChange={(e)=>setProfileForm({ ...profileForm, name: e.target.value })} sx={{ mb: 1 }} />
                            <TextField size="small" fullWidth label="Post" value={(profileForm.post as string) || ''} onChange={(e)=>setProfileForm({ ...profileForm, post: e.target.value })} sx={{ mb: 1 }} />
                            <TextField size="small" fullWidth label="District" value={(profileForm.district as string) || ''} onChange={(e)=>setProfileForm({ ...profileForm, district: e.target.value })} sx={{ mb: 1 }} />
                            <TextField size="small" fullWidth label="Thana" value={(profileForm.thana as string) || ''} onChange={(e)=>setProfileForm({ ...profileForm, thana: e.target.value })} sx={{ mb: 1 }} />
                            <Box sx={{ display: 'flex', gap: 1 }}>
                                <Button size="small" startIcon={<Save />} variant="contained" onClick={saveProfile}>Save</Button>
                                <Button size="small" startIcon={<Cancel />} onClick={()=>{ setProfileEdit(false); setProfileErr(null); }}>Cancel</Button>
                            </Box>
                        </Box>
                    )}
                    {pwFormOpen && (
                        <Box sx={{ mt: 1 }}>
                            <TextField size="small" fullWidth label="Current Password" type="password" value={pwCurrent} onChange={(e)=>setPwCurrent(e.target.value)} sx={{ mb: 1 }} />
                            <TextField size="small" fullWidth label="New Password" type="password" value={pwNew} onChange={(e)=>setPwNew(e.target.value)} sx={{ mb: 1 }} />
                            <TextField size="small" fullWidth label="Confirm New Password" type="password" value={pwConfirm} onChange={(e)=>setPwConfirm(e.target.value)} sx={{ mb: 1 }} />
                            <Button size="small" variant="contained" startIcon={<LockReset />} onClick={changePassword}>Update Password</Button>
                        </Box>
                    )}
                </Box>
            </Drawer>

            {/* Main content */}
            <Box component="main" sx={{ flexGrow: 1, ml: `${drawerWidth}px`, px: 2, maxWidth: '100%' }}>
            <Box sx={{ my: 4 }}>
                <Typography variant="h4" component="h1" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
                    <Security sx={{ mr: 2, color: 'primary.main' }} />
                    IPDR Analysis Dashboard
                </Typography>
                
                <Paper elevation={3} sx={{ p: 3, mb: 4 }}>
                    <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center' }}>
                        <UploadFile sx={{ mr: 1 }} />
                        Process IPDR Data
                    </Typography>
                    <Button 
                        sx={{ mt: 2 }} 
                        variant="contained" 
                        color="primary" 
                        onClick={handleProcessData} 
                        disabled={uploading}
                        startIcon={uploading ? <CircularProgress size={20} /> : null}
                    >
                        {uploading ? 'Processing...' : 'Process Data'}
                    </Button>
                    {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
                    {uploadResponse && (
                        <Alert severity="success" sx={{ mt: 2 }}>
                            {`${uploadResponse.message} Found ${uploadResponse.records_found} records.`}
                        </Alert>
                    )}
                </Paper>
            {dashboardStats && (
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3, mb: 4 }}>
                        <Box sx={{ minWidth: 250, flex: 1 }}>
                            <Card>
                                <CardContent>
                                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                        <Box>
                                            <Typography color="textSecondary" gutterBottom>Total Records</Typography>
                                            <Typography variant="h5" component="div">{dashboardStats.total_records.toLocaleString()}</Typography>
                                        </Box>
                                        <Timeline color="primary" sx={{ fontSize: 40 }} />
                                    </Box>
                                </CardContent>
                            </Card>
                        </Box>
                        <Box sx={{ minWidth: 250, flex: 1 }}>
                            <Card>
                                <CardContent>
                                     <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                        <Box>
                                            <Typography color="textSecondary" gutterBottom>Unique Phones</Typography>
                                            <Typography variant="h5" component="div">{dashboardStats.unique_phones.toLocaleString()}</Typography>
                                        </Box>
                                        <Phone color="success" sx={{ fontSize: 40 }} />
                                    </Box>
                                </CardContent>
                            </Card>
                        </Box>
                        <Box sx={{ minWidth: 250, flex: 1 }}>
                            <Card>
                                <CardContent>
                                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                        <Box>
                                            <Typography color="textSecondary" gutterBottom>IP Addresses</Typography>
                                            <Typography variant="h5" component="div">{dashboardStats.unique_ips.toLocaleString()}</Typography>
                                        </Box>
                                        <Wifi color="info" sx={{ fontSize: 40 }} />
                                    </Box>
                                </CardContent>
                            </Card>
                        </Box>
                        <Box sx={{ minWidth: 250, flex: 1 }}>
                            <Card>
                                <CardContent>
                                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                        <Box>
                                            <Typography color="textSecondary" gutterBottom>Suspicious Activities</Typography>
                                            <Typography variant="h5" component="div">
                                                {dashboardStats.suspicious_activities}
                                            </Typography>
                                        </Box>
                                        <Warning color="error" sx={{ fontSize: 40 }} />
                                    </Box>
                                </CardContent>
                            </Card>
                        </Box>
                    </Box>
                )}

                {uploadResponse && uploadResponse.records_found > 0 && (
                    <Paper elevation={3} sx={{ mb: 4 }}>
                        {/* Navigation moved to left drawer */}

                        {activeTab === 0 && (
                            <Box sx={{ p: 3 }}>
                                <Typography variant="h6" gutterBottom>Extracted Phone Numbers & Profiles</Typography>
                                <TableContainer>
                                    <Table>
                                        <TableHead>
                                            <TableRow>
                                                <TableCell><strong>Phone Number</strong></TableCell>
                                                <TableCell><strong>Customer Name</strong></TableCell>
                                                <TableCell><strong>Subscriber ID</strong></TableCell>
                                                <TableCell><strong>Total Calls</strong></TableCell>
                                                <TableCell><strong>Risk Level</strong></TableCell>
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {extractedNumbers.map((number, index) => (
                                                <TableRow key={index} hover>
                                                    <TableCell><Chip label={number.phone} color="primary" size="small" onClick={() => {setPhoneSearchQuery(number.phone); setActiveTab(3);}}/></TableCell>
                                                    <TableCell>{number.customer_name}</TableCell>
                                                    <TableCell>{number.subscriber_id}</TableCell>
                                                    <TableCell><Badge badgeContent={number.total_calls} color="info" /></TableCell>
                                                    <TableCell><Chip label={number.risk_level} sx={{ backgroundColor: getRiskColor(number.risk_level), color: 'white' }} size="small"/></TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                            </Box>
                        )}
                        
                        {activeTab === 1 && (
                             <Box sx={{ p: 3 }}>
                                <Typography variant="h6" gutterBottom>Communication Relationships Analysis</Typography>
                                <TableContainer>
                                    <Table size="small">
                                        <TableHead>
                                            <TableRow>
                                                <TableCell><strong>Source</strong></TableCell>
                                                <TableCell><strong>Destination</strong></TableCell>
                                                <TableCell><strong>Call Count</strong></TableCell>
                                                <TableCell><strong>Total Duration (min)</strong></TableCell>
                                                <TableCell><strong>Strength</strong></TableCell>
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {callRelationships.map((rel, index) => (
                                                <TableRow key={index} hover>
                                                    <TableCell><Chip label={rel.source} color="secondary" size="small"/></TableCell>
                                                    <TableCell><Chip label={rel.destination} color="primary" size="small"/></TableCell>
                                                    <TableCell><Badge badgeContent={rel.call_count} color="info" /></TableCell>
                                                    <TableCell>{Math.round(rel.total_duration / 60)}</TableCell>
                                                    <TableCell><LinearProgress variant="determinate" value={rel.relationship_strength} sx={{ width: 60 }}/></TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                            </Box>
                        )}

                        {activeTab === 2 && (
                             <Box sx={{ p: 3 }}>
                                <Typography variant="h6" gutterBottom>Suspicious Activities & Red Flags</Typography>
                                {suspiciousActivities.length === 0 ? (
                                    <Alert severity="success">No Suspicious Activities Detected</Alert>
                                ) : (
                                    <List>
                                        {suspiciousActivities.map((activity) => (
                                            <React.Fragment key={activity.id}>
                                                <ListItemButton onClick={() => toggleAlertExpand(activity.id)}>
                                                    <ListItemIcon><Warning color={getSeverityColorForIcon(activity.severity) as any} /></ListItemIcon>
                                                    <ListItemText
                                                        primary={<>{activity.type} <Chip label={activity.severity} color={getSeverityColorForChip(activity.severity)} size="small"/></>}
                                                        secondary={<>{activity.description} {activity.phone && `- Phone: ${activity.phone}`} {activity.ip && `- IP: ${activity.ip}`} @ {new Date(activity.timestamp).toLocaleString()}</>}
                                                    />
                                                    {expandedAlerts.has(activity.id) ? <ExpandLess /> : <ExpandMore />}
                                                </ListItemButton>
                                                <Collapse in={expandedAlerts.has(activity.id)} timeout="auto" unmountOnExit>
                                                    <Box sx={{ pl: 7, pr: 2, pb: 2 }}>
                                                        <Paper variant="outlined" sx={{ p: 2 }}>
                                                            <Typography variant="subtitle2" gutterBottom>Suspect Details</Typography>
                                                            <Table size="small">
                                                                <TableBody>
                                                                    {detailRowsForAlert(activity).map((row, idx) => (
                                                                        <TableRow key={idx}>
                                                                            <TableCell sx={{ width: 220 }}><strong>{row.label}</strong></TableCell>
                                                                            <TableCell>{String(row.value)}</TableCell>
                                                                        </TableRow>
                                                                    ))}
                                                                </TableBody>
                                                            </Table>
                                                            <Box sx={{ mt: 1, display: 'flex', gap: 1 }}>
                                                                {activity.phone && (
                                                                    <Button size="small" variant="outlined" onClick={() => { setActiveTab(3); setPhoneSearchQuery(activity.phone!); setTimeout(()=>handleSearch('phone'), 0); }}>Search Phone</Button>
                                                                )}
                                                                {activity.ip && (
                                                                    <Button size="small" variant="outlined" onClick={() => { setActiveTab(3); setIpSearchQuery(activity.ip!); setTimeout(()=>handleSearch('ip'), 0); }}>Search IP</Button>
                                                                )}
                                                            </Box>
                                                        </Paper>
                                                    </Box>
                                                </Collapse>
                                                <Divider />
                                            </React.Fragment>
                                        ))}
                                    </List>
                                )}
                            </Box>
                        )}

                        {activeTab === 3 && (
                            <Box sx={{ p: 3 }}>
                                <Typography variant="h6" gutterBottom>Search & Query Interface</Typography>
                                <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 3, mb: 3 }}>
                                    <Box sx={{ flex: 1 }}>
                                        <Box sx={{ display: 'flex', gap: 2 }}>
                                            <TextField fullWidth label="Enter phone number" value={phoneSearchQuery} onChange={(e) => setPhoneSearchQuery(e.target.value)} />
                                            <Button variant="contained" onClick={() => handleSearch('phone')} disabled={!phoneSearchQuery}>Search</Button>
                                        </Box>
                                    </Box>
                                    <Box sx={{ flex: 1 }}>
                                        <Box sx={{ display: 'flex', gap: 2 }}>
                                            <TextField fullWidth label="Enter IP address" value={ipSearchQuery} onChange={(e) => setIpSearchQuery(e.target.value)} />
                                            <Button variant="contained" onClick={() => handleSearch('ip')} disabled={!ipSearchQuery}>Search</Button>
                                        </Box>
                                    </Box>
                                </Box>

                                {loadingData ? <CircularProgress /> : rows.length > 0 && (
                                    <Paper variant="outlined" sx={{ height: 400, width: '100%' }}>
                                        <DataGrid rows={rows} columns={columns} pageSizeOptions={[10]} checkboxSelection />
                                    </Paper>
                                )}
                            </Box>
                        )}

                        {activeTab === 4 && (
                            <Box sx={{ p: 3 }}>
                                <Typography variant="h6" gutterBottom>Network Graph Visualization</Typography>
                                <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
                                    <Button 
                                        variant="outlined" 
                                        size="small" 
                                        onClick={() => fetchGraphData(25)}
                                    >
                                        Small Graph (25 nodes)
                                    </Button>
                                    <Button 
                                        variant="outlined" 
                                        size="small" 
                                        onClick={() => fetchGraphData(50)}
                                    >
                                        Medium Graph (50 nodes)
                                    </Button>
                                    <Button 
                                        variant="outlined" 
                                        size="small" 
                                        onClick={() => fetchGraphData(100)}
                                    >
                                        Large Graph (100 nodes)
                                    </Button>
                                </Box>
                                <Paper variant="outlined" sx={{ p: 2, height: '600px', mb: 2 }}>
                                    {graphData.nodes.length > 0 ? (
                                        <Graph
                                            key={`graph-${graphData.nodes.length}-${graphData.edges.length}`}
                                            graph={{
                                                // Deduplicate nodes by stable backend id and keep the same id to avoid patch collisions
                                                nodes: Array.from(new Map(graphData.nodes.map(n => [n.id, n])).values()).map(node => ({
                                                    id: node.id,
                                                    label: node.label,
                                                    color: node.label.startsWith('+')
                                                        ? { background: '#4CAF50', border: '#2E7D32' }  // Green for phones
                                                        : { background: '#2196F3', border: '#1976D2' }, // Blue for IPs
                                                    font: { color: 'white', size: 12 },
                                                    shape: node.label.startsWith('+') ? 'circle' : 'box'
                                                })),
                                                edges: (() => {
                                                    // Deduplicate edges by (from,to) pair and use stable ids from backend
                                                    const edgeSet = new Set<string>();
                                                    const uniq: { from: string; to: string }[] = [];
                                                    for (const e of graphData.edges) {
                                                        const key = `${e.from}->${e.to}`;
                                                        if (!edgeSet.has(key)) {
                                                            edgeSet.add(key);
                                                            uniq.push({ from: e.from, to: e.to });
                                                        }
                                                    }
                                                    return uniq.map((edge, index) => ({
                                                        id: `edge-${index}`,
                                                        from: edge.from,
                                                        to: edge.to,
                                                        color: { color: '#848484' },
                                                        arrows: { to: { enabled: true } }
                                                    }));
                                                })()
                                            }}
                                            options={{
                                                layout: {
                                                    hierarchical: false
                                                },
                                                edges: {
                                                    color: "#848484",
                                                    arrows: { to: { enabled: true } }
                                                },
                                                physics: {
                                                    enabled: true,
                                                    stabilization: { iterations: 200 }
                                                },
                                                nodes: {
                                                    font: { color: 'white' },
                                                    borderWidth: 2
                                                },
                                                height: '550px'
                                            }}
                                            events={{
                                                select: (event) => {
                                                    const { nodes } = event;
                                                    if (nodes.length > 0) {
                                                        const nodeId: string = nodes[0];
                                                        if (nodeId.startsWith('ip:')) {
                                                            const ip = nodeId.substring(3);
                                                            setIpLookup(ip);
                                                            enrichIp(ip);
                                                        }
                                                    }
                                                }
                                            }}
                                        />
                                    ) : (
                                        <Box sx={{ 
                                            display: 'flex', 
                                            alignItems: 'center', 
                                            justifyContent: 'center', 
                                            height: '100%',
                                            flexDirection: 'column'
                                        }}>
                                            <Typography variant="h6" color="textSecondary" gutterBottom>
                                                No Network Data Available
                                            </Typography>
                                            <Typography variant="body2" color="textSecondary">
                                                Process the IPDR data first to see the communication network visualization.
                                            </Typography>
                                        </Box>
                                    )}
                                </Paper>
                                <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
                                    <Chip icon={<Phone />} label="Phone Numbers" sx={{ backgroundColor: '#4CAF50', color: 'white' }} />
                                    <Chip icon={<Wifi />} label="IP Addresses" sx={{ backgroundColor: '#2196F3', color: 'white' }} />
                                </Box>
                                <Typography variant="body2" color="textSecondary">
                                    The graph shows communication patterns: Phone numbers (green circles) → Source IPs (blue boxes) → Destination IPs (blue boxes)
                                </Typography>
                            </Box>
                        )}
                        
                        {activeTab === 5 && (
                            <Box sx={{ p: 3 }}>
                                <Typography variant="h6" gutterBottom>Raw Communication Data</Typography>
                                <TextField fullWidth label="Search all data..." variant="outlined" value={searchQuery} onChange={handleSearchChange} sx={{ mb: 2 }} />
                                {loadingData ? <CircularProgress /> : (
                                    <Box sx={{ height: 600, width: '100%' }}>
                                        <DataGrid rows={rows} columns={columns} pageSizeOptions={[25, 50, 100]} checkboxSelection />
                                    </Box>
                                )}
                            </Box>
                        )}

                        {activeTab === 6 && (
                            <Box sx={{ p: 3 }}>
                                <Typography variant="h6" gutterBottom>B‑Party Summary</Typography>
                                <Typography variant="subtitle2" sx={{ mt: 1, mb: 1 }}>B‑Party Phones</Typography>
                                <TableContainer sx={{ mb: 2 }}>
                                    <Table size="small">
                                        <TableHead>
                                            <TableRow>
                                                <TableCell><strong>Phone</strong></TableCell>
                                                <TableCell><strong>Total</strong></TableCell>
                                                <TableCell><strong>Unique Sources</strong></TableCell>
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {bpartyPhones.map((p: any, i: number) => (
                                                <TableRow key={`bpp-${i}`}>
                                                    <TableCell><Chip size="small" label={p.phone} onClick={()=>{ setPhoneSearchQuery(p.phone); setActiveTab(3); }} /></TableCell>
                                                    <TableCell>{p.total}</TableCell>
                                                    <TableCell>{p.unique_sources}</TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </TableContainer>

                                <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>B‑Party Public IPs</Typography>
                                <TableContainer>
                                    <Table size="small">
                                        <TableHead>
                                            <TableRow>
                                                <TableCell><strong>IP</strong></TableCell>
                                                <TableCell><strong>Public</strong></TableCell>
                                                <TableCell><strong>Category</strong></TableCell>
                                                <TableCell><strong>Total</strong></TableCell>
                                                <TableCell><strong>Unique Sources</strong></TableCell>
                                                <TableCell><strong>Top Ports</strong></TableCell>
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {bpartyIPs.map((r: any, i: number) => (
                                                <TableRow key={`bpip-${i}`}>
                                                    <TableCell><Chip size="small" label={r.ip} onClick={()=>{ setIpSearchQuery(r.ip); setActiveTab(3); }} /></TableCell>
                                                    <TableCell>{r.is_public ? 'Yes' : 'No'}</TableCell>
                                                    <TableCell>{r.ip_category}</TableCell>
                                                    <TableCell>{r.total}</TableCell>
                                                    <TableCell>{r.unique_sources}</TableCell>
                                                    <TableCell>{r.top_ports}</TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                            </Box>
                        )}

                        {activeTab === 7 && (
                            <Box sx={{ p: 3 }}>
                                <Typography variant="h6" gutterBottom>Normalization & Investigation Filters</Typography>
                                <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
                                    <Card sx={{ minWidth: 260 }}>
                                        <CardContent>
                                            <Typography color="textSecondary" gutterBottom>Normalization Stats</Typography>
                                            <Typography variant="body2">Files: {normalizationStats?.total_files_processed ?? 0}</Typography>
                                            <Typography variant="body2">Success: {normalizationStats?.successful_normalizations ?? 0}</Typography>
                                            <Typography variant="body2">Records: {normalizationStats?.total_records_processed ?? 0}</Typography>
                                        </CardContent>
                                    </Card>
                                    <Card sx={{ minWidth: 260 }}>
                                        <CardContent>
                                            <Typography color="textSecondary" gutterBottom>Run Investigation Filters</Typography>
                                            <Button variant="contained" size="small" onClick={runInvestigationFilters}>RUN</Button>
                                            {!filterStats && (
                                                <Typography variant="body2" sx={{ mt: 1 }} color="textSecondary">Not run yet</Typography>
                                            )}
                                            {filterStats && (
                                                <Box sx={{ mt: 1 }}>
                                                    <Typography variant="body2">Original: {filterStats.summary?.original_records ?? '-'}</Typography>
                                                    <Typography variant="body2">Filtered: {filterStats.summary?.filtered_records ?? '-'}</Typography>
                                                    <Typography variant="body2">Excluded: {filterStats.summary?.excluded_records ?? '-'}</Typography>
                                                </Box>
                                            )}
                                        </CardContent>
                                    </Card>
                                </Box>
                            </Box>
                        )}

                        {activeTab === 8 && (
                            <Box sx={{ p: 3 }}>
                                <Typography variant="h6" gutterBottom>Cases & Saved Searches</Typography>
                                <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2 }}>
                                    <TextField size="small" label="New Case Name" value={newCaseName} onChange={(e)=>setNewCaseName(e.target.value)} />
                                    <Button variant="contained" size="small" onClick={createCase}>Create</Button>
                                    <FormControl size="small" sx={{ minWidth: 200 }}>
                                        <InputLabel id="case-select-label">Select Case</InputLabel>
                                        <Select labelId="case-select-label" label="Select Case" value={selectedCaseId} onChange={(e)=>{ const id = e.target.value as number; setSelectedCaseId(id); if(id) loadSavedSearches(id); }}>
                                            <MenuItem value=""><em>None</em></MenuItem>
                                            {cases.map((c:any)=> (<MenuItem key={c.id} value={c.id}>{c.name}</MenuItem>))}
                                        </Select>
                                    </FormControl>
                                    <Button variant="outlined" size="small" onClick={exportCasePack} disabled={!selectedCaseId}>Export Pack</Button>
                                </Box>

                                <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2 }}>
                                    <TextField size="small" fullWidth label="Notes (optional)" value={saveNotes} onChange={(e)=>setSaveNotes(e.target.value)} />
                                    <Button variant="contained" size="small" onClick={saveCurrentSearchToCase} disabled={!selectedCaseId || !lastSearchCriteria}>Save Current Search to Case</Button>
                                </Box>

                                <Typography variant="subtitle2" gutterBottom>Saved Searches</Typography>
                                <List>
                                    {savedSearches.map((s:any)=> (
                                        <ListItem key={s.id}>
                                            <ListItemText primary={s.notes || `Search #${s.id}`} secondary={s.created_at} />
                                        </ListItem>
                                    ))}
                                </List>
                            </Box>
                        )}

                        {activeTab === 9 && (
                            <Box sx={{ p: 3 }}>
                                <Typography variant="h6" gutterBottom>IP Enrichment (Offline Cache)</Typography>
                                <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
                                    <TextField size="small" label="Enter IP" value={ipLookup} onChange={(e)=>setIpLookup(e.target.value)} />
                                    <Button variant="contained" size="small" onClick={()=>enrichIp(ipLookup)} disabled={!ipLookup}>Enrich</Button>
                                </Box>
                                {ipEnrichment && (
                                    <Paper variant="outlined" sx={{ p: 2 }}>
                                        <Typography variant="body2">IP: {ipEnrichment.ip}</Typography>
                                        <Typography variant="body2">Public: {String(ipEnrichment.is_public)}</Typography>
                                        <Typography variant="body2">Category: {ipEnrichment.category}</Typography>
                                        <Typography variant="body2">ASN: {ipEnrichment.asn || '-'}</Typography>
                                        <Typography variant="body2">Org: {ipEnrichment.org || '-'}</Typography>
                                        <Typography variant="body2">Country: {ipEnrichment.country || '-'}</Typography>
                                    </Paper>
                                )}
                            </Box>
                        )}

                        {activeTab === 10 && (
                            <Box sx={{ p: 3 }}>
                                <Typography variant="h6" gutterBottom>Correlation (A → B) — Connecting the Dots</Typography>
                                <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
                                    <Button variant="outlined" size="small" onClick={()=>fetchCorrelation(50)}>Top 50 Edges</Button>
                                    <Button variant="outlined" size="small" onClick={()=>fetchCorrelation(100)}>Top 100 Edges</Button>
                                    <Button variant="outlined" size="small" onClick={()=>fetchCorrelation(200)}>Top 200 Edges</Button>
                                </Box>
                                <Paper variant="outlined" sx={{ p: 2, height: '600px', mb: 2 }}>
                                    {corrNodes.length > 0 ? (
                                        <Graph
                                            key={`corr-${corrNodes.length}-${corrEdges.length}`}
                                            graph={{
                                                nodes: Array.from(new Map(corrNodes.map(n=>[n.id,n])).values()).map(node=>({
                                                    id: node.id,
                                                    label: node.label,
                                                    color: node.id.startsWith('a:') ? { background: '#7E57C2', border: '#5E35B1' } : { background: '#26A69A', border: '#00897B' },
                                                    font: { color: 'white', size: 12 },
                                                    shape: node.label.startsWith('+') ? 'circle' : 'box'
                                                })),
                                                edges: (()=>{
                                                    const set = new Set<string>();
                                                    const uniq: any[] = [];
                                                    for (const e of corrEdges) {
                                                        const k = `${e.from}->${e.to}`;
                                                        if (!set.has(k)) { set.add(k); uniq.push(e); }
                                                    }
                                                    return uniq.map((e, i)=>({ id: `ce-${i}`, from: e.from, to: e.to, value: e.value, color: { color: '#9E9E9E' } }));
                                                })()
                                            }}
                                            options={{
                                                layout: { hierarchical: { enabled: true, direction: 'LR', levelSeparation: 200, nodeSpacing: 150 } },
                                                edges: { smooth: true },
                                                physics: { enabled: false },
                                                nodes: { font: { color: 'white' }, borderWidth: 2 },
                                                height: '550px'
                                            }}
                                        />
                                    ) : (
                                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                                            <Typography color="textSecondary">No correlation data. Process data first.</Typography>
                                        </Box>
                                    )}
                                </Paper>
                                <Typography variant="subtitle2" gutterBottom>Top A→B Pairs</Typography>
                                <TableContainer>
                                    <Table size="small">
                                        <TableHead>
                                            <TableRow>
                                                <TableCell><strong>A‑Party</strong></TableCell>
                                                <TableCell><strong>B‑Party</strong></TableCell>
                                                <TableCell><strong>Count</strong></TableCell>
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {corrTopPairs.map((p:any, idx:number)=> (
                                                <TableRow key={idx}>
                                                    <TableCell>{p.a}</TableCell>
                                                    <TableCell>{p.b}</TableCell>
                                                    <TableCell>{p.count}</TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                            </Box>
                        )}

                        {activeTab === 11 && (
                            <Box sx={{ p: 3 }}>
                                <Typography variant="h6" gutterBottom>Geo Maps</Typography>
                                <Box sx={{ display: 'flex', gap: 2, flexDirection: 'column' }}>
                                    <Paper variant="outlined" sx={{ p: 2 }}>
                                        <Typography variant="subtitle1" gutterBottom>Suspicious Phones — Last 7 Days</Typography>
                                        <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
                                            <Button size="small" variant="outlined" onClick={()=> setSuspMapSrc(`${API_URL}/map/suspicious-phones/html?days=7`)}>REFRESH</Button>
                                        </Box>
                                        {suspMapSrc ? (
                                            <iframe title="suspicious-map" src={suspMapSrc} style={{ width: '100%', height: 620, border: 0, borderRadius: 6 }} />
                                        ) : (
                                            <Typography color="textSecondary">Click REFRESH to load map.</Typography>
                                        )}
                                    </Paper>

                                    <Paper variant="outlined" sx={{ p: 2 }}>
                                        <Typography variant="subtitle1" gutterBottom>Two‑Person Conversation Map</Typography>
                                        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 1, flexWrap: 'wrap' }}>
                                            <TextField size="small" label="Phone A (caller)" value={convA} onChange={(e)=>setConvA(e.target.value.replace(/[^0-9]/g, ''))} inputProps={{ inputMode: 'numeric', pattern: '[0-9]*' }} helperText="Enter 10 or 12 digits (no + or country code)" />
                                            <TextField size="small" label="Phone B (callee)" value={convB} onChange={(e)=>setConvB(e.target.value.replace(/[^0-9]/g, ''))} inputProps={{ inputMode: 'numeric', pattern: '[0-9]*' }} helperText="Enter 10 or 12 digits (no + or country code)" />
                                            <Button size="small" variant="contained" onClick={()=> {
                                                const toE164 = (p: string) => {
                                                    const digits = (p || '').replace(/[^0-9]/g,'');
                                                    if (digits.length === 10) return `+91${digits}`;
                                                    if (digits.length === 12 && digits.startsWith('91')) return `+${digits}`;
                                                    if (digits.length === 11 && digits.startsWith('0')) return `+91${digits.slice(1)}`;
                                                    return digits ? `+${digits}` : '';
                                                };
                                                const a = toE164(convA);
                                                const b = toE164(convB);
                                                setConvMapSrc(`${API_URL}/map/conversation/html?phone_a=${encodeURIComponent(a)}&phone_b=${encodeURIComponent(b)}&days=7`);
                                            }} disabled={!convA || !convB}>PLOT</Button>
                                        </Box>
                                        {convMapSrc ? (
                                            <iframe title="conversation-map" src={convMapSrc} style={{ width: '100%', height: 620, border: 0, borderRadius: 6 }} />
                                        ) : (
                                            <Typography color="textSecondary">Enter Phone A and Phone B, then click PLOT.</Typography>
                                        )}
                                    </Paper>

                                    {/* Link Analysis section removed as per requirements */}
                                </Box>
                            </Box>
                        )}
                    </Paper>
                )}
                
                {dashboardStats && (
                    <Paper elevation={1} sx={{ p: 2, textAlign: 'center', mt: 2 }}>
                        <Typography variant="body2" color="textSecondary">
                            <AccessTime sx={{ mr: 1, verticalAlign: 'middle' }} />
                            Analysis Period: {dashboardStats.time_range}
                        </Typography>
                    </Paper>
                )}
            </Box>
        </Box>
        </Box>
    );
};

export default Dashboard;
