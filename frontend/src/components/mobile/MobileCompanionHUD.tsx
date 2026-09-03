import React, { useState, useEffect } from "react";
import { Smartphone, QrCode, ShieldCheck, Key, Trash2, RefreshCw, Lock } from "lucide-react";
import { apiUrl } from "../../lib/backend";

interface PairedDevice {
  device_id: string;
  device_name: string;
  platform: string;
  app_version?: string;
  is_biometric_enabled: boolean;
  status: string;
}

interface HardwarePasskey {
  credential_id: string;
  device_name: string;
  sign_count: number;
  status: string;
}

interface QrData {
  pairing_token: string;
  host_url: string;
  expires_at: number;
}

export const MobileCompanionHUD: React.FC = () => {
  const [devices, setDevices] = useState<PairedDevice[]>([]);
  const [passkeys, setPasskeys] = useState<HardwarePasskey[]>([]);
  const [qrData, setQrData] = useState<QrData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const fetchMobileData = () => {
    setIsLoading(true);
    fetch(apiUrl("/api/v1/mobile/devices"))
      .then((res) => res.json())
      .then((data) => {
        if (data.devices) setDevices(data.devices);
      })
      .catch(() => {})
      .finally(() => setIsLoading(false));

    fetch(apiUrl("/api/v1/security/passkey/list"))
      .then((res) => res.json())
      .then((data) => {
        if (data.passkeys) setPasskeys(data.passkeys);
      })
      .catch(() => {});
  };

  const generateNewQr = () => {
    fetch(apiUrl("/api/v1/mobile/pairing-qr"))
      .then((res) => res.json())
      .then((data) => setQrData(data))
      .catch(() => {});
  };

  useEffect(() => {
    fetchMobileData();
    generateNewQr();
  }, []);

  const revokeDevice = (deviceId: string) => {
    fetch(apiUrl("/api/v1/mobile/revoke"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_id: deviceId }),
    })
      .then(() => fetchMobileData())
      .catch(() => {});
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-y-auto p-4 select-none font-mono space-y-4">
      {/* Header */}
      <div className="pb-3 border-b border-surface-border flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <Smartphone className="w-5 h-5 text-accent" />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">
              MOBILE COMPANION & HARDWARE PASSKEY ENCLAVE
            </h2>
          </div>
          <p className="text-xs text-slate-400">
            Encrypted iOS / Android Companion Bridge & FIDO2 WebAuthn Hardware Security
          </p>
        </div>

        <button
          onClick={fetchMobileData}
          disabled={isLoading}
          className="p-1.5 bg-[#0d121c] hover:bg-[#111722] border border-surface-border rounded text-slate-400 hover:text-white transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* QR Code Pairing Panel */}
        <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-3 flex flex-col justify-between">
          <div className="flex items-center justify-between border-b border-surface-border pb-2">
            <span className="text-xs font-bold text-white flex items-center space-x-1.5">
              <QrCode className="w-4 h-4 text-accent" />
              <span>PAIR NEW MOBILE DEVICE (BIOMETRIC QR)</span>
            </span>
            <button
              onClick={generateNewQr}
              className="text-[10px] text-accent hover:underline flex items-center space-x-1"
            >
              <RefreshCw className="w-3 h-3" />
              <span>REFRESH TOKEN</span>
            </button>
          </div>

          <div className="flex items-center space-x-4 py-2">
            {/* Visual QR Code Mock Block */}
            <div className="w-32 h-32 bg-white rounded-lg p-2 flex flex-col items-center justify-center space-y-1 shadow-md">
              <QrCode className="w-20 h-20 text-black" />
              <span className="text-[8px] text-black font-bold font-mono">KUANTRA-PAIR</span>
            </div>

            <div className="flex-1 space-y-1.5 text-xs">
              <span className="text-[10px] text-slate-400 block">PAIRING TOKEN:</span>
              <span className="font-bold text-accent font-mono text-xs block bg-[#111722] p-1.5 rounded border border-surface-border">
                {qrData?.pairing_token || "GENERATING..."}
              </span>
              <p className="text-[10px] text-slate-400">
                Scan with Kuantra Mobile App (iOS / Android) to pair securely via Argon2id session handshake.
              </p>
            </div>
          </div>
        </div>

        {/* FIDO2 Hardware Passkey Enclave */}
        <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-3 flex flex-col justify-between">
          <div className="flex items-center justify-between border-b border-surface-border pb-2">
            <span className="text-xs font-bold text-white flex items-center space-x-1.5">
              <Key className="w-4 h-4 text-purple-400" />
              <span>FIDO2 / WEBAUTHN HARDWARE ENCLAVE</span>
            </span>
            <span className="text-[10px] bg-purple-500/20 text-purple-300 px-2 py-0.5 rounded font-bold">
              ORDER SHIELD &gt; $50K
            </span>
          </div>

          <div className="space-y-2 overflow-y-auto max-h-36">
            {passkeys.map((pk) => (
              <div
                key={pk.credential_id}
                className="bg-[#111722] p-2.5 rounded border border-surface-border flex items-center justify-between text-xs"
              >
                <div className="space-y-0.5">
                  <span className="font-bold text-white block">{pk.device_name}</span>
                  <span className="text-[10px] text-slate-400 font-mono">{pk.credential_id}</span>
                </div>
                <div className="flex items-center space-x-1 text-[10px] text-gain font-bold">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>ARMED</span>
                </div>
              </div>
            ))}
          </div>

          <div className="text-[10px] text-slate-400 flex items-center space-x-1">
            <Lock className="w-3 h-3 text-purple-400" />
            <span>Hardware challenge automatically triggered for orders &gt; $50,000.</span>
          </div>
        </div>
      </div>

      {/* Authorized Paired Mobile Devices */}
      <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-3">
        <div className="flex items-center justify-between border-b border-surface-border pb-2">
          <span className="text-xs font-bold text-white flex items-center space-x-1.5">
            <Smartphone className="w-4 h-4 text-gain" />
            <span>AUTHORIZED MOBILE COMPANIONS</span>
          </span>
          <span className="text-[10px] text-slate-400">{devices.length} Paired Devices</span>
        </div>

        <div className="space-y-2">
          {devices.map((dev) => (
            <div
              key={dev.device_id}
              className="bg-[#111722] p-3 rounded border border-surface-border flex items-center justify-between text-xs"
            >
              <div className="space-y-0.5">
                <div className="flex items-center space-x-2">
                  <span className="font-bold text-white">{dev.device_name}</span>
                  <span className="text-[10px] bg-accent/15 text-accent px-1.5 rounded font-bold">
                    {dev.platform}
                  </span>
                  {dev.is_biometric_enabled && (
                    <span className="text-[10px] bg-gain/15 text-gain px-1.5 rounded font-bold">
                      BIOMETRICS ON
                    </span>
                  )}
                </div>
                <div className="text-[10px] text-slate-500 font-mono">{dev.device_id}</div>
              </div>

              <div className="flex items-center space-x-3">
                <span className="text-[10px] bg-gain/20 text-gain px-2 py-0.5 rounded font-bold">
                  {dev.status}
                </span>

                <button
                  onClick={() => revokeDevice(dev.device_id)}
                  className="p-1 text-slate-400 hover:text-rose-500 hover:bg-rose-500/10 rounded transition"
                  title="Revoke Device"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};