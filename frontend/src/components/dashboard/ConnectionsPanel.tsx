import { useMemo, useState } from 'react';
import type { ConnectionSyncEvent, DataConnection } from '../../types';

type ProviderOption = {
  provider_name: string;
  provider_slug: string;
};

type ConnectionsPanelProps = {
  loading: boolean;
  connections: DataConnection[];
  syncEvents: ConnectionSyncEvent[];
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
  syncEvents,
  availableProviders,
  activeConnectionSlug,
  activeSyncConnectionId,
  onConnectProvider,
  onToggleConnection,
  onSyncConnection,
  formatDate,
}: ConnectionsPanelProps) {
  const [providerSearch, setProviderSearch] = useState('');
  const [showProviderPicker, setShowProviderPicker] = useState(false);
  const [showAllProviders, setShowAllProviders] = useState(false);

  const filteredProviders = useMemo(() => {
    const normalizedQuery = providerSearch.trim().toLowerCase();
    if (!normalizedQuery) return availableProviders;
    return availableProviders.filter((provider) =>
      provider.provider_name.toLowerCase().includes(normalizedQuery),
    );
  }, [availableProviders, providerSearch]);
  const connectedCount = useMemo(
    () => connections.filter((connection) => connection.is_active).length,
    [connections],
  );
  const visibleProviders = useMemo(
    () => filteredProviders.slice(0, showAllProviders ? 12 : 4),
    [filteredProviders, showAllProviders],
  );
  const hasMoreProviders = filteredProviders.length > visibleProviders.length;
  const quickConnectProviders = useMemo(() => availableProviders.slice(0, 2), [availableProviders]);

  return (
    <div className="insight-panel connection-panel">
      <div className="insight-panel-header">
        <div>
          <p className="eyebrow">Connections</p>
          <h2>Data sources</h2>
          <p className="subtitle">
            Kenya-first sync for DHA, SHR, KHIS, and partner platforms using HL7/FHIR-aligned workflows.
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
        <div className="provider-rail">
          <div className="provider-rail-header">
            <p className="provider-rail-summary">
              {connectedCount} connected · {availableProviders.length} available to add
            </p>
            <button
              type="button"
              className="ghost-button compact"
              onClick={() => setShowProviderPicker((prev) => !prev)}
            >
              {showProviderPicker
                ? 'Hide providers'
                : connections.length
                  ? 'Connect provider'
                  : 'Add first provider'}
            </button>
          </div>
          {!showProviderPicker && connections.length === 0 && quickConnectProviders.length ? (
            <div className="provider-quick-actions">
              {quickConnectProviders.map((provider) => (
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
          {showProviderPicker ? (
            <div className="provider-chip-row">
              <input
                type="search"
                className="connection-provider-search"
                placeholder="Search providers..."
                value={providerSearch}
                onChange={(event) => setProviderSearch(event.target.value)}
                aria-label="Search providers"
              />
              {visibleProviders.map((provider) => (
                <button
                  key={provider.provider_slug}
                  type="button"
                  className="provider-chip"
                  onClick={() => {
                    onConnectProvider(provider.provider_name, provider.provider_slug);
                    if (!connections.length) {
                      setShowProviderPicker(false);
                    }
                  }}
                  disabled={activeConnectionSlug !== null}
                >
                  {activeConnectionSlug === provider.provider_slug
                    ? 'Connecting…'
                    : `Connect ${provider.provider_name}`}
                </button>
              ))}
              {providerSearch.trim() && filteredProviders.length === 0 ? (
                <p className="dashboard-empty">No providers match that search.</p>
              ) : null}
              {hasMoreProviders ? (
                <button
                  type="button"
                  className="ghost-button compact provider-more-button"
                  onClick={() => setShowAllProviders(true)}
                  disabled={activeConnectionSlug !== null}
                >
                  Show more providers
                </button>
              ) : null}
              {!hasMoreProviders && showAllProviders && filteredProviders.length > 4 ? (
                <button
                  type="button"
                  className="ghost-button compact provider-more-button"
                  onClick={() => setShowAllProviders(false)}
                >
                  Show fewer providers
                </button>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
      {syncEvents.length ? (
        <div className="connection-events">
          <p className="eyebrow">Recent sync activity</p>
          <ul className="connection-events-list">
            {syncEvents.slice(0, 5).map((event) => (
              <li key={event.id} className="connection-event-item">
                <strong>{event.provider_slug.replace(/_/g, ' ')}</strong>
                <span>{event.event_type.replace(/_/g, ' ')}</span>
                <span>{formatDate(event.created_at)}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

export default ConnectionsPanel;
