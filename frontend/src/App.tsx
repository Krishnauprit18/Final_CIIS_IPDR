import { useEffect, useState } from 'react';
import './App.css';
import { CssBaseline, ThemeProvider, createTheme, Box, AppBar, Toolbar, Typography, Button } from '@mui/material';
import { Logout } from '@mui/icons-material';
import Dashboard from './Dashboard';
import Login from './Login';
import Register from './Register';
import LogoBadge from './LogoBadge';
import { logout, verifySession } from './auth/api';

let verifyEffectHasRun = false;

const darkTheme = createTheme({
    palette: {
        mode: 'dark',
    },
});

interface User {
    username: string;
    token: string;
}

function App() {
    const [user, setUser] = useState<User | null>(null);
    const [showRegister, setShowRegister] = useState(false);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (verifyEffectHasRun) {
            setLoading(false);
            return;
        }
        verifyEffectHasRun = true;

        const storedToken = localStorage.getItem('ipdr_token');
        const storedUsername = localStorage.getItem('ipdr_username');

        if (storedToken && storedUsername) {
            verifySession()
                .then(() => setUser({ username: storedUsername, token: storedToken }))
                .catch(() => {
                    localStorage.removeItem('ipdr_token');
                    localStorage.removeItem('ipdr_username');
                })
                .finally(() => setLoading(false));
        } else {
            setLoading(false);
        }
    }, []);

    const handleLogin = (userData: User) => {
        setUser(userData);
        localStorage.setItem('ipdr_token', userData.token);
        localStorage.setItem('ipdr_username', userData.username);
    };

    const handleLogout = async () => {
        try {
            await logout();
        } catch (error) {
            console.error('Logout error:', error);
        } finally {
            setUser(null);
            localStorage.removeItem('ipdr_token');
            localStorage.removeItem('ipdr_username');
        }
    };

    if (loading) {
        return (
            <ThemeProvider theme={darkTheme}>
                <CssBaseline />
                <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
                    <Typography>Loading...</Typography>
                </Box>
            </ThemeProvider>
        );
    }

    return (
        <ThemeProvider theme={darkTheme}>
            <CssBaseline />
            {user ? (
                <>
                    <LogoBadge width={150} top={12} left={12} />
                    <Box>
                        <AppBar position="static" sx={{ width: { md: 'calc(100% - 220px)' }, ml: { md: '220px' } }}>
                            <Toolbar>
                                <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
                                    IPDR Analysis Dashboard
                                </Typography>
                                <Typography variant="body2" sx={{ mr: 2 }}>Welcome, {user.username}</Typography>
                                <Button color="inherit" onClick={handleLogout} startIcon={<Logout />}>Logout</Button>
                            </Toolbar>
                        </AppBar>
                        <Dashboard />
                    </Box>
                </>
            ) : (
                showRegister ? (
                    <Register onRegistered={handleLogin} onShowLogin={() => setShowRegister(false)} />
                ) : (
                    <Login onLogin={handleLogin} onShowRegister={() => setShowRegister(true)} />
                )
            )}
        </ThemeProvider>
    );
}

export default App;
