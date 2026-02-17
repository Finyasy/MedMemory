import type { DataConnection } from '../../types';

type ProviderOption = {
  provider_name: string;
  provider_slug: string;
};

type ConnectionsPanelProps = {
  loading: boolean;
  connections: DataConnection[];
  availableProviders: ProviderOption[];
  activeConnectionSlug: string | null;
  activeSyncConnectionId: number | null;
  onConnectProvider: (providerName: string, providerSlug: string) => void;
  onToggleConnection: (connection: DataConnection) => void;
  onSyncConnection: (connection: DataConnection) => void;
  formatDate: (date: string) => string;
};

function ConnectionsPanel({
  loading,
  connections,
  availableProviders,
  activeConnectionSlug,
  activeSyncConnectionId,
  onConnectProvider,
  onToggleConnection,
  onSyncConnection,
  formatDate,
}: ConnectionsPanelProps) {
  return (
    <div className="insight-panel connection-panel">
      <div className="insight-panel-header">
        <div>
          <p className="eyebrow">Connections</p>
          <h2>Data sources</h2>
          <p className="subtitle">
            Sync hospitals, labs, and wellness providers so summaries use full context.
          </p>
        </div>
      </div>
      {loading ? (
        <p className="dashboard-empty">Loading connections…</p>
      ) : connections.length ? (
        <ul className="connection-list">
          {connections.map((connection) => (
            <li key={connection.id} className="connection-item">
              <div className="connection-meta">
                <div className="connection-title-row">
                  <h4>{connection.provider_name}</h4>
                  <span className={`connection-status status-${connection.status}`}>
                    {connection.status}
                  </span>
                </div>
                <p>
                  {connection.source_count} source{connection.source_count === 1 ? '' : 's'} ·{' '}
                  {connection.last_synced_at
                    ? `last sync ${formatDate(connection.last_synced_at)}`
                    : 'not synced yet'}
                </p>
                {connection.last_error ? (
                  <p className="connection-error">{connection.last_error}</p>
                ) : null}
              </div>
              <div className="connection-actions">
                <button
                  type="button"
                  className="ghost-button compact"
                  onClick={() => onSyncConnection(connection)}
                  disabled={
                    !connection.is_active ||
                    activeSyncConnectionId === connection.id ||
                    activeConnectionSlug !== null
                  }
                >
                  {activeSyncConnectionId === connection.id ? 'Syncing…' : 'Sync now'}
                </button>
                <button
                  type="button"
                  className="secondary-button compact"
                  onClick={() => onToggleConnection(connection)}
                  disabled={activeConnectionSlug !== null || activeSyncConnectionId !== null}
                >
                  {activeConnectionSlug === connection.provider_slug
                    ? 'Updating…'
                    : connection.is_active
                      ? 'Disconnect'
                      : 'Reconnect'}
                </button>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="dashboard-empty">
          No providers connected yet. Connect one below to start syncing data.
        </p>
      )}
      {availableProviders.length ? (
        <div className="provider-chip-row">
          {availableProviders.slice(0, 6).map((provider) => (
            <button
              key={provider.provider_slug}
              type="button"
              className="provider-chip"
              onClick={() => onConnectProvider(provider.provider_name, provider.provider_slug)}
              disabled={activeConnectionSlug !== null}
            >
              {activeConnectionSlug === provider.provider_slug
                ? 'Connecting…'
                : `Connect ${provider.provider_name}`}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export default ConnectionsPanel;
