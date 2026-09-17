import React, { useMemo, useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Container,
  TextField,
  Button,
  Typography,
  Alert,
  InputAdornment,
  IconButton,
  Divider
} from '@mui/material';
import Grid from '@mui/material/Grid';
import { Person, Email, Visibility, VisibilityOff, Badge, LocationOn, Shield, Refresh } from '@mui/icons-material';
import { register } from './auth/api';

interface RegisterProps {
  onRegistered: (user: { username: string; token: string }) => void;
  onShowLogin: () => void;
}

const Register: React.FC<RegisterProps> = ({ onShowLogin }) => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [post, setPost] = useState('');
  const [district, setDistrict] = useState('');
  const [thana, setThana] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [showPw2, setShowPw2] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [captcha, setCaptcha] = useState('');
  const [captchaInput, setCaptchaInput] = useState('');

  const generateCaptcha = () => {
    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789';
    let v = '';
    for (let i = 0; i < 5; i++) v += chars[Math.floor(Math.random() * chars.length)];
    return v;
  };

  useMemo(() => {
    setCaptcha(generateCaptcha());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setInfo(null);

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError('Please enter a valid official email');
      return;
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }
    if (captchaInput.trim() !== captcha.trim()) {
      setError('Invalid captcha. Please try again.');
      setCaptcha(generateCaptcha());
      return;
    }

    setLoading(true);
    try {
      const data = await register({ name, email, password, post, district, thana });
      if (data?.success) {
        onShowLogin();
      } else {
        setInfo(data?.message || 'Registration submitted');
      }
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Registration failed';
      setError(String(msg));
    } finally {
      setLoading(false);
    }
  };

  const disabled = !name || !email || !password || !confirmPassword || !post || !district || !thana || !captchaInput;

  return (
    <Box
      sx={{
        minHeight: '100vh',
        backgroundImage: 'url(/assets/security-bg.jpg)',
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        p: 2,
      }}
    >
      <Container maxWidth="sm">
        <Card className="login-card" sx={{ overflow: 'hidden', borderRadius: 3, boxShadow: 8 }}>
          <CardContent sx={{ p: 4, position: 'relative' }}>
            <Shield sx={{ position: 'absolute', right: 16, top: 16, fontSize: 48, color: 'primary.light', opacity: 0.15 }} />

            <Box sx={{ textAlign: 'center', mb: 2 }}>
              <img
                src="/assets/mp-police-logo.png"
                alt="MP Police"
                onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
                style={{ width: 80, height: 'auto', objectFit: 'contain', marginBottom: 8 }}
              />
              <Typography variant="h5" sx={{ fontWeight: 700 }}>Create Account</Typography>
              <Typography variant="body2" color="text.secondary">Official Registration</Typography>
            </Box>

            <Divider sx={{ my: 2 }} />

            <form onSubmit={handleSubmit}>
              <Grid container spacing={2}>
                <Grid size={12}>
                  <TextField
                    fullWidth
                    label="Name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    InputProps={{ startAdornment: (<InputAdornment position="start"><Person /></InputAdornment>) }}
                  />
                </Grid>
                <Grid size={12}>
                  <TextField
                    fullWidth
                    label="Official Email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    InputProps={{ startAdornment: (<InputAdornment position="start"><Email /></InputAdornment>) }}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    fullWidth
                    label="Password"
                    type={showPw ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    InputProps={{
                      endAdornment: (
                        <InputAdornment position="end">
                          <IconButton onClick={() => setShowPw(!showPw)}>{showPw ? <VisibilityOff /> : <Visibility />}</IconButton>
                        </InputAdornment>
                      ),
                    }}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    fullWidth
                    label="Enter password again"
                    type={showPw2 ? 'text' : 'password'}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    InputProps={{
                      endAdornment: (
                        <InputAdornment position="end">
                          <IconButton onClick={() => setShowPw2(!showPw2)}>{showPw2 ? <VisibilityOff /> : <Visibility />}</IconButton>
                        </InputAdornment>
                      ),
                    }}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    fullWidth
                    label="Post"
                    value={post}
                    onChange={(e) => setPost(e.target.value)}
                    InputProps={{ startAdornment: (<InputAdornment position="start"><Badge /></InputAdornment>) }}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    fullWidth
                    label="District"
                    value={district}
                    onChange={(e) => setDistrict(e.target.value)}
                    InputProps={{ startAdornment: (<InputAdornment position="start"><LocationOn /></InputAdornment>) }}
                  />
                </Grid>
                <Grid size={12}>
                  <TextField
                    fullWidth
                    label="Police Thana Location"
                    value={thana}
                    onChange={(e) => setThana(e.target.value)}
                    InputProps={{ startAdornment: (<InputAdornment position="start"><LocationOn /></InputAdornment>) }}
                  />
                </Grid>
                <Grid size={12}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Box
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
                    <TextField label="Captcha code" value={captchaInput} onChange={(e) => setCaptchaInput(e.target.value)} fullWidth />
                  </Box>
                </Grid>
              </Grid>

              {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
              {info && <Alert severity="info" sx={{ mt: 2 }}>{info}</Alert>}

              <Button type="submit" variant="contained" size="large" fullWidth disabled={loading || disabled} sx={{ mt: 3, py: 1.4, borderRadius: 999 }}>
                {loading ? 'Submitting...' : 'Register'}
              </Button>
              <Button type="button" color="inherit" fullWidth onClick={onShowLogin} sx={{ mt: 1 }}>
                Back to Login
              </Button>
            </form>
          </CardContent>
        </Card>
      </Container>
    </Box>
  );
};

export default Register;
