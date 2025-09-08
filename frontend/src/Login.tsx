import React, { useMemo, useState } from 'react';
import {
    Container, TextField, Button, Typography, Alert, Box,
    Card, CardContent, IconButton, InputAdornment, Divider
} from '@mui/material';
import { Security, Visibility, VisibilityOff, Person, Refresh } from '@mui/icons-material';
import axios from 'axios';
import LogoBadge from './LogoBadge';

const API_URL = 'http://localhost:8000';

interface LoginProps {
    onLogin: (user: { username: string; token: string }) => void;
    onShowRegister?: () => void;
}

const Login: React.FC<LoginProps> = ({ onLogin, onShowRegister }) => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [captcha, setCaptcha] = useState<string>('');
    const [captchaInput, setCaptchaInput] = useState<string>('');

    const generateCaptcha = () => {
        const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789';
        let v = '';
        for (let i = 0; i < 4; i++) v += chars[Math.floor(Math.random() * chars.length)];
        return v;
    };

    useMemo(() => {
        setCaptcha(generateCaptcha());
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);

        try {
            if (captchaInput.trim() !== captcha.trim()) {
                setError('Invalid captcha. Please try again.');
                setCaptcha(generateCaptcha());
                return;
            }
            const response = await axios.post(`${API_URL}/auth/login`, {
                username,
                password
            });

            if (response.data.success) {
                onLogin({
                    username: response.data.username,
                    token: response.data.token
                });
            } else {
                setError(response.data.message || 'Login failed');
            }
        } catch (err: any) {
            setError(err.response?.data?.message || 'Login failed. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <Box
            className="login-page"
            sx={{
                minHeight: '100vh',
                background: 'linear-gradient(135deg, #1e88e5 0%, #1565c0 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                p: 2,
                position: 'relative',
                '&::before': {
                    content: '""',
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    background: 'url(/login1.jpeg) center/cover no-repeat',
                    opacity: 0.3,
                    filter: 'brightness(1.2)',
                    zIndex: 0
                },
                '&::after': {
                    content: '""',
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    background: 'radial-gradient(circle at 30% 50%, rgba(33,150,243,0.4) 0%, transparent 70%)',
                    zIndex: 1
                }
            }}
        >
            {/* Page-level top-left emblem as a separate component */}
            <LogoBadge width={150} top={12} left={12} />
            <Container maxWidth="sm" sx={{ position: 'relative' }}>
                <Card 
                    className="login-card" 
                    sx={{ 
                        width: '100%', 
                        maxWidth: 430, 
                        mx: 'auto', 
                        overflow: 'hidden', 
                        borderRadius: 3, 
                        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
                        position: 'relative',
                        background: 'linear-gradient(145deg, #1a237e 0%, #0d47a1 100%)',
                        backdropFilter: 'blur(20px)',
                        border: '1px solid rgba(255, 255, 255, 0.1)',
                        zIndex: 2
                    }}
                >
                    <CardContent sx={{ p: 4, position: 'relative' }}>
                        {/* Right background shield icon */}
                        <Security sx={{ position: 'absolute', right: 16, top: 16, fontSize: 48, color: 'primary.light', opacity: 0.15 }} />

                        {/* Top logos */}
                        <Box sx={{ textAlign: 'center', mb: 2 }}>
                            {/* MP Police official logo placeholder */}
                            <img
                                src="/assets/mp-police-logo.png"
                                alt="MP Police"
                                onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
                                style={{ width: 80, height: 'auto', objectFit: 'contain', marginBottom: 8 }}
                            />
                            <Typography 
                                variant="h5" 
                                sx={{
                                    fontWeight: 700,
                                    color: '#ffffff',
                                    textShadow: '0 2px 4px rgba(0,0,0,0.2)',
                                    letterSpacing: '0.5px',
                                    fontSize: '1.8rem',
                                    mb: 1
                                }}
                            >
                                Secure Access Portal
                            </Typography>
                            <Typography 
                                variant="body2" 
                                sx={{ 
                                    color: 'text.secondary',
                                    letterSpacing: '1px',
                                    textTransform: 'uppercase',
                                    opacity: 0.8
                                }}
                            >
                                IPDR Analysis
                            </Typography>
                        </Box>

                        <Divider sx={{ my: 2 }} />

                        {/* Project logo area */}
                        <ProjectLogo />

                        <form onSubmit={handleSubmit}>
                            <TextField
                                fullWidth
                                label="User name / Email"
                                variant="outlined"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                required
                                margin="normal"
                                sx={{
                                    '& .MuiOutlinedInput-root': {
                                        backgroundColor: 'rgba(255, 255, 255, 0.1)',
                                        transition: 'all 0.3s',
                                        borderColor: 'rgba(255, 255, 255, 0.3)',
                                        boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
                                        color: '#ffffff',
                                        '&:hover': {
                                            backgroundColor: 'rgba(255, 255, 255, 0.15)',
                                            borderColor: 'rgba(255, 255, 255, 0.5)'
                                        },
                                        '&.Mui-focused': {
                                            backgroundColor: 'rgba(255, 255, 255, 0.15)',
                                            borderColor: 'rgba(255, 255, 255, 0.7)',
                                            boxShadow: '0 4px 8px rgba(0,0,0,0.2)'
                                        }
                                    },
                                    '& .MuiInputLabel-root': {
                                        color: 'rgba(255, 255, 255, 0.7)'
                                    },
                                    '& .MuiOutlinedInput-notchedOutline': {
                                        borderColor: 'rgba(255, 255, 255, 0.3)'
                                    },
                                    '& .MuiInputAdornment-root': {
                                        color: 'rgba(255, 255, 255, 0.7)'
                                    }
                                }}
                                InputProps={{
                                    startAdornment: (
                                        <InputAdornment position="start">
                                            <Person />
                                        </InputAdornment>
                                    ),
                                }}
                            />

                            <TextField
                                fullWidth
                                label="Password"
                                type={showPassword ? 'text' : 'password'}
                                variant="outlined"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                                margin="normal"
                                InputProps={{
                                    endAdornment: (
                                        <InputAdornment position="end">
                                            <IconButton onClick={() => setShowPassword(!showPassword)} edge="end" aria-label="toggle password">
                                                {showPassword ? <VisibilityOff /> : <Visibility />}
                                            </IconButton>
                                        </InputAdornment>
                                    ),
                                }}
                            />

                            {/* Captcha row */}
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
                                <Box
                                    aria-label="captcha"
                                    sx={{
                                        fontFamily: 'monospace',
                                        fontSize: 22,
                                        letterSpacing: 1,
                                        bgcolor: 'background.default',
                                        px: 1.5,
                                        py: 0.75,
                                        borderRadius: 1,
                                        border: '1px solid',
                                        borderColor: 'divider',
                                        textDecoration: 'line-through',
                                        userSelect: 'none'
                                    }}
                                >
                                    {captcha}
                                </Box>
                                <IconButton aria-label="refresh captcha" onClick={() => { setCaptcha(generateCaptcha()); setCaptchaInput(''); }}>
                                    <Refresh />
                                </IconButton>
                                <TextField
                                    fullWidth
                                    label="Captcha code"
                                    value={captchaInput}
                                    onChange={(e) => setCaptchaInput(e.target.value)}
                                />
                            </Box>

                            {error && (
                                <Alert severity="error" sx={{ mt: 2 }}>
                                    {error}
                                </Alert>
                            )}

                            <Button
                                type="submit"
                                fullWidth
                                variant="contained"
                                size="large"
                                disabled={loading || !username || !password || !captchaInput}
                                sx={{ 
                                    mt: 3, 
                                    mb: 1, 
                                    py: 1.4, 
                                    borderRadius: '50px',
                                    background: 'linear-gradient(45deg, #64b5f6 30%, #2196f3 90%)',
                                    boxShadow: '0 3px 5px 2px rgba(33, 150, 243, .3)',
                                    transition: 'all 0.3s ease-in-out',
                                    color: '#1a237e',
                                    fontWeight: 'bold',
                                    '&:hover': {
                                        transform: 'translateY(-2px)',
                                        boxShadow: '0 6px 10px 4px rgba(33, 150, 243, .3)',
                                        background: 'linear-gradient(45deg, #90caf9 30%, #42a5f5 90%)'
                                    }
                                }}
                            >
                                {loading ? 'Logging in...' : 'LOG IN NOW'}
                            </Button>
                        </form>

                        {/* Link to registration page */}
                        <Button color="inherit" fullWidth onClick={() => onShowRegister && onShowRegister()} sx={{ mt: 1 }}>
                            New user? Register
                        </Button>
                    </CardContent>
                </Card>
            </Container>
        </Box>
    );
};

export default Login;
// Inline component to render project logo in login page with multiple fallbacks
const ProjectLogo: React.FC = () => {
    return (
        <Box className="project-logo" sx={{ mb: 2.5, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <img
                src="/Logo.png"
                alt="Project Logo"
                style={{
                    width: '100%',
                    height: 200,
                    maxWidth: 400,
                    objectFit: 'contain'
                }}
            />
        </Box>
    );
};
