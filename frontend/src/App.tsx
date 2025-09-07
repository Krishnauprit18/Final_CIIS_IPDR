import { useState, useEffect } from 'react';
import './App.css';
import { CssBaseline, ThemeProvider, createTheme, Box, AppBar, Toolbar, Typography, Button } from '@mui/material';
import { Logout } from '@mui/icons-material';
import Dashboard from './Dashboard';
import Login from './Login';
import Register from './Register';
import axios from 'axios';

// Module-scope guard to avoid duplicate verify calls in React.StrictMode (dev-only double mount)
let verifyEffectHasRun = false;

const API_URL = 'http://localhost:8000';

// A simple dark theme for the dashboard
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

    // Check for existing session on app start
    // Avoid duplicate verify calls in React.StrictMode (dev) by using a module-scope guard
    useEffect(() => {
        if (verifyEffectHasRun) {
            setLoading(false);
            return;
        }
        verifyEffectHasRun = true;

        const storedToken = localStorage.getItem('ipdr_token');
        const storedUsername = localStorage.getItem('ipdr_username');
        
        if (storedToken && storedUsername) {
            // Verify token with backend
            axios.get(`${API_URL}/auth/verify`, {
                headers: { Authorization: `Bearer ${storedToken}` }
            }).then(() => {
                setUser({ username: storedUsername, token: storedToken });
                // Set default auth header for axios
                axios.defaults.headers.common['Authorization'] = `Bearer ${storedToken}`;
            }).catch(() => {
                // Token is invalid, clear storage
                localStorage.removeItem('ipdr_token');
                localStorage.removeItem('ipdr_username');
            }).finally(() => {
                setLoading(false);
            });
        } else {
            setLoading(false);
        }

        return () => {};
    }, []);

    const handleLogin = (userData: User) => {
        setUser(userData);
        localStorage.setItem('ipdr_token', userData.token);
        localStorage.setItem('ipdr_username', userData.username);
        // Set default auth header for axios
        axios.defaults.headers.common['Authorization'] = `Bearer ${userData.token}`;
    };

    const handleLogout = async () => {
        try {
            await axios.post(`${API_URL}/auth/logout`);
        } catch (error) {
            console.error('Logout error:', error);
        } finally {
            setUser(null);
            localStorage.removeItem('ipdr_token');
            localStorage.removeItem('ipdr_username');
            delete axios.defaults.headers.common['Authorization'];
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
                <Box>
                    <AppBar position="static">
                        <Toolbar>
                            <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
                                IPDR Analysis Dashboard
                            </Typography>
                            <Typography variant="body2" sx={{ mr: 2 }}>
                                Welcome, {user.username}
                            </Typography>
                            <Button 
                                color="inherit" 
                                onClick={handleLogout}
                                startIcon={<Logout />}
                            >
                                Logout
                            </Button>
                        </Toolbar>
                    </AppBar>
                    <Dashboard />
                </Box>
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
