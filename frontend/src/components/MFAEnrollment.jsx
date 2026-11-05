import { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import apiClient from '../utils/api';
import { toast } from 'sonner';

const MFAEnrollment = ({ onEnrollmentComplete }) => {
  const { user } = useAuth();
  const [step, setStep] = useState('display'); // display, verify, success
  const [qrCodeUrl, setQrCodeUrl] = useState('');
  const [manualSecret, setManualSecret] = useState('');
  const [verificationCode, setVerificationCode] = useState('');
  const [backupCodes, setBackupCodes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleStartEnrollment = async () => {
    try {
      setLoading(true);
      setError('');
      
      const response = await apiClient.post('/auth/mfa/enroll');
      setQrCodeUrl(response.data.qr_code_url);
      setManualSecret(response.data.manual_secret);
      setStep('verify');
      
      toast.success('MFA enrollment started. Scan the QR code with your authenticator app.');
    } catch (err) {
      console.error('Failed to start MFA enrollment:', err);
      setError('Failed to start MFA enrollment. Please try again.');
      toast.error('Failed to start MFA enrollment');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyEnrollment = async () => {
    try {
      setLoading(true);
      setError('');
      
      if (verificationCode.length !== 6) {
        setError('Please enter a 6-digit code');
        setLoading(false);
        return;
      }
      
      const response = await apiClient.post('/auth/mfa/verify-enrollment', {
        code: verificationCode,
        trust_device: false
      });
      
      setBackupCodes(response.data.backup_codes);
      setStep('success');
      
      toast.success('MFA enabled successfully! Save your backup codes securely.');
      
      if (onEnrollmentComplete) {
        onEnrollmentComplete();
      }
    } catch (err) {
      console.error('Failed to verify MFA enrollment:', err);
      setError('Invalid code. Please try again.');
      toast.error('Invalid MFA code');
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadBackupCodes = () => {
    const text = backupCodes.join('\n');
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'mfa-backup-codes.txt';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    toast.success('Backup codes downloaded');
  };

  const handleCopyBackupCodes = () => {
    const text = backupCodes.join('\n');
    navigator.clipboard.writeText(text);
    toast.success('Backup codes copied to clipboard');
  };

  if (step === 'display') {
    return (
      <div className="mfa-enrollment">
        <div className="max-w-md mx-auto bg-white border border-border p-8">
          <h2 className="text-2xl font-bold text-primary mb-4">Enable Multi-Factor Authentication</h2>
          <p className="text-muted mb-6">
            Add an extra layer of security to your account by enabling MFA. 
            You'll need to enter a code from your authenticator app each time you log in.
          </p>
          
          <div className="bg-blue-50 border border-blue-200 p-4 mb-6">
            <p className="text-sm text-blue-800">
              <strong>Why MFA?</strong> MFA protects your account even if your password is compromised. 
              It's required for all privileged users (super_admin, business_admin, staff).
            </p>
          </div>
          
          <button
            onClick={handleStartEnrollment}
            disabled={loading}
            className="w-full bg-primary text-white px-6 py-3 font-bold tracking-wide border border-primary hover:bg-[#333333] transition-all disabled:opacity-50"
          >
            {loading ? 'Starting...' : 'Enable MFA'}
          </button>
        </div>
      </div>
    );
  }

  if (step === 'verify') {
    return (
      <div className="mfa-enrollment">
        <div className="max-w-md mx-auto bg-white border border-border p-8">
          <h2 className="text-2xl font-bold text-primary mb-4">Set Up Authenticator App</h2>
          
          <div className="mb-6">
            <h3 className="font-semibold mb-2">Step 1: Download an Authenticator App</h3>
            <p className="text-sm text-muted mb-4">
              Download one of these apps on your mobile device:
            </p>
            <ul className="text-sm text-muted space-y-1 mb-4">
              <li>• Google Authenticator (iOS, Android)</li>
              <li>• Authy (iOS, Android)</li>
              <li>• Microsoft Authenticator (iOS, Android)</li>
            </ul>
          </div>
          
          <div className="mb-6">
            <h3 className="font-semibold mb-2">Step 2: Scan the QR Code</h3>
            <div className="flex justify-center mb-4">
              <img 
                src={qrCodeUrl} 
                alt="QR Code for MFA Setup" 
                className="w-48 h-48 border border-border"
              />
            </div>
            <p className="text-sm text-muted text-center mb-4">
              Scan this QR code with your authenticator app
            </p>
          </div>
          
          <div className="mb-6">
            <h3 className="font-semibold mb-2">Step 3: Enter Verification Code</h3>
            <p className="text-sm text-muted mb-2">
              Enter the 6-digit code from your authenticator app to verify setup
            </p>
            <input
              type="text"
              value={verificationCode}
              onChange={(e) => setVerificationCode(e.target.value)}
              placeholder="123456"
              maxLength={6}
              className="w-full border border-border px-4 py-2 text-center text-2xl tracking-widest"
            />
            {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
          </div>
          
          <div className="mb-6">
            <details className="text-sm">
              <summary className="cursor-pointer text-primary hover:underline">
                Can't scan QR code? Enter manually
              </summary>
              <div className="mt-2 p-4 bg-gray-50 border border-border">
                <p className="font-semibold mb-2">Manual Entry Code:</p>
                <code className="block p-2 bg-white border border-border break-all">
                  {manualSecret}
                </code>
                <p className="text-xs text-muted mt-2">
                  Enter this code in your authenticator app instead of scanning
                </p>
              </div>
            </details>
          </div>
          
          <button
            onClick={handleVerifyEnrollment}
            disabled={loading || verificationCode.length !== 6}
            className="w-full bg-primary text-white px-6 py-3 font-bold tracking-wide border border-primary hover:bg-[#333333] transition-all disabled:opacity-50"
          >
            {loading ? 'Verifying...' : 'Verify and Enable MFA'}
          </button>
          
          <button
            onClick={() => setStep('display')}
            className="w-full mt-4 text-muted hover:text-primary transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  if (step === 'success') {
    return (
      <div className="mfa-enrollment">
        <div className="max-w-md mx-auto bg-white border border-border p-8">
          <div className="text-center mb-6">
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold text-primary mb-2">MFA Enabled Successfully!</h2>
            <p className="text-muted">
              Your account is now protected with multi-factor authentication.
            </p>
          </div>
          
          <div className="bg-yellow-50 border border-yellow-200 p-4 mb-6">
            <h3 className="font-semibold text-yellow-800 mb-2">⚠️ Save Your Backup Codes</h3>
            <p className="text-sm text-yellow-800 mb-4">
              These backup codes can be used to recover your account if you lose access to your authenticator app. 
              Save them in a secure location.
            </p>
            
            <div className="bg-white border border-border p-4 mb-4">
              <ul className="space-y-1">
                {backupCodes.map((code, index) => (
                  <li key={index} className="font-mono text-lg">{code}</li>
                ))}
              </ul>
            </div>
            
            <div className="flex gap-2">
              <button
                onClick={handleDownloadBackupCodes}
                className="flex-1 bg-primary text-white px-4 py-2 font-bold tracking-wide border border-primary hover:bg-[#333333] transition-all"
              >
                Download
              </button>
              <button
                onClick={handleCopyBackupCodes}
                className="flex-1 bg-white text-primary px-4 py-2 font-bold tracking-wide border border-primary hover:bg-gray-50 transition-all"
              >
                Copy
              </button>
            </div>
          </div>
          
          <div className="bg-blue-50 border border-blue-200 p-4 mb-6">
            <h3 className="font-semibold text-blue-800 mb-2">What's Next?</h3>
            <ul className="text-sm text-blue-800 space-y-1">
              <li>• You'll be prompted for MFA code when logging in</li>
              <li>• Your code changes every 30 seconds</li>
              <li>• Use backup codes if you lose your authenticator</li>
              <li>• Contact support if you lose access to all codes</li>
            </ul>
          </div>
          
          <button
            onClick={() => {
              setStep('display');
              setQrCodeUrl('');
              setManualSecret('');
              setVerificationCode('');
              setBackupCodes([]);
              setError('');
            }}
            className="w-full text-muted hover:text-primary transition-colors"
          >
            Complete
          </button>
        </div>
      </div>
    );
  }

  return null;
};

export default MFAEnrollment;