import React, { useState, useEffect } from "react";
import { Share2, ShieldCheck, Activity, Radio, Lock, RefreshCw, Send, CheckCircle2 } from "lucide-react";
import { apiFetch, apiUrl } from "../../lib/backend";

interface Peer {
  peer_id: string;
  node_name: string;
  pubkey: string;
  endpoint: string;
  role: string;
  handshake_status: string;
  protocol: string;
  latency_ms: number;
}

interface MeshStatus {
  node_id: string;
  node_name: string;
  role: string;
  public_key: string;
  is_active: boolean;
  peers_count: number;
  noise_protocol: string;
  peers: Peer[];
}

export const MeshNetworkHUD: React.FC = () => {
  const [status, setStatus] = useState<MeshStatus>({
    node_id: "12D3KooWc5c97f6c637c2946",
    node_name: "Kuantra-Mesh-01",
    role: "FOLLOWER",
    public_key: "pubkey-master-778899aabbcc",
    is_active: true,
    peers_count: 2,
    noise_protocol: "Noise_IK_25519_ChaChaPoly_BLAKE2s",
    peers: [],
  });

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [broadcastMsg, setBroadcastMsg] = useState<string | null>(null);

  const fetchMeshStatus = () => {
    setIsLoading(true);
    apiFetch(apiUrl("/api/v1/p2p/status"))
      .then((res) => res.json())
      .then((data) => setStatus(data))
      .catch(() => {})
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    fetchMeshStatus();
    const interval = setInterval(fetchMeshStatus, 3000);
    return () => clearInterval(interval);
  }, []);

  const broadcastTestSignal = async () => {
    try {
      const res = await apiFetch(apiUrl("/api/v1/p2p/copy/broadcast"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: "BTCUSDT",
          side: "BUY",
          entry_price: 64900.0,
          stop_loss: 64000.0,
          take_profit: 67200.0,
          risk_pct: 1.0,
          notes: "Zero-Knowledge Signal via Noise Protocol Mesh",
        }),
      });
      const data = await res.json();
      setBroadcastMsg(`Signal ${data.signal_id} cryptographically broadcasted to ${status.peers_count} mesh peers.`);
      setTimeout(() => setBroadcastMsg(null), 5000);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-y-auto p-4 select-none font-mono space-y-4">
      {/* Header */}
      <div className="pb-3 border-b border-surface-border flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <Share2 className="w-5 h-5 text-accent" />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">
              ENCRYPTED P2P SIGNAL MESH NETWORK
            </h2>
          </div>
          <p className="text-xs text-slate-400">
            Serverless Gossip Routing with Noise Protocol Framework (Noise_IK_25519)
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={broadcastTestSignal}
            className="flex items-center space-x-1.5 bg-accent hover:bg-sky-400 text-black font-bold px-3 py-1.5 rounded text-xs transition"
          >
            <Send className="w-3.5 h-3.5" />
            <span>BROADCAST MASTER SIGNAL</span>
          </button>

          <button
            onClick={fetchMeshStatus}
            disabled={isLoading}
            className="p-1.5 bg-[#0d121c] hover:bg-[#111722] border border-surface-border rounded text-slate-400 hover:text-white transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Broadcast Alert */}
      {broadcastMsg && (
        <div className="bg-gain/10 border border-gain/30 p-3 rounded-lg flex items-center space-x-2 text-gain text-xs">
          <CheckCircle2 className="w-4 h-4 text-gain" />
          <span>{broadcastMsg}</span>
        </div>
      )}

      {/* Local Node Identity Strip */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <div className="bg-[#0d121c] p-3 rounded border border-surface-border">
          <span className="text-[10px] text-slate-400 block">LOCAL PEER ID</span>
          <span className="text-xs font-bold text-accent truncate block">{status.node_id}</span>
        </div>
        <div className="bg-[#0d121c] p-3 rounded border border-surface-border">
          <span className="text-[10px] text-slate-400 block">ENCRYPTION PROTOCOL</span>
          <span className="text-xs font-bold text-white flex items-center space-x-1">
            <Lock className="w-3 h-3 text-purple-400" />
            <span className="truncate">{status.noise_protocol}</span>
          </span>
        </div>
        <div className="bg-[#0d121c] p-3 rounded border border-surface-border">
          <span className="text-[10px] text-slate-400 block">NODE ROLE</span>
          <span className="text-xs font-bold text-white">{status.role}</span>
        </div>
        <div className="bg-[#0d121c] p-3 rounded border border-surface-border">
          <span className="text-[10px] text-slate-400 block">ACTIVE MESH PEERS</span>
          <div className="flex items-center space-x-1.5">
            <Radio className="w-3.5 h-3.5 text-gain animate-pulse" />
            <span className="text-sm font-bold text-gain font-mono">{status.peers_count} Connected</span>
          </div>
        </div>
      </div>

      {/* Connected Peers Table */}
      <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-3">
        <div className="flex items-center justify-between border-b border-surface-border pb-2">
          <span className="text-xs font-bold text-white flex items-center space-x-1.5">
            <Activity className="w-4 h-4 text-accent" />
            <span>DISCOVERED P2P NODES & HANDSHAKE MATRIX</span>
          </span>
          <span className="text-[10px] text-slate-400">Noise IK Session Keys Active</span>
        </div>

        <div className="space-y-2">
          {status.peers.map((peer) => (
            <div
              key={peer.peer_id}
              className="bg-[#111722] p-3 rounded border border-surface-border flex items-center justify-between text-xs"
            >
              <div className="space-y-0.5">
                <div className="flex items-center space-x-2">
                  <span className="font-bold text-white">{peer.node_name}</span>
                  <span className="text-[10px] bg-accent/15 text-accent px-1.5 rounded font-bold">
                    {peer.role}
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">{peer.endpoint}</span>
                </div>
                <div className="text-[10px] text-slate-400 font-mono truncate max-w-md">
                  Pubkey: {peer.pubkey}
                </div>
              </div>

              <div className="flex items-center space-x-4">
                <div className="text-right">
                  <span className="text-[10px] text-slate-400 block">LATENCY</span>
                  <span className="text-xs font-bold text-gain font-mono">{peer.latency_ms} ms</span>
                </div>

                <div className="flex items-center space-x-1 bg-gain/10 border border-gain/30 px-2 py-1 rounded text-[10px] text-gain font-bold">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>{peer.handshake_status}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};