import type { MemorySearchResult } from '../types';

type MemoryPanelProps = {
  query: string;
  isLoading: boolean;
  results: MemorySearchResult[];
  isDisabled?: boolean;
  onQueryChange: (value: string) => void;
  onSearch: () => void;
};

const MemoryPanel = ({
  query,
  isLoading,
  results,
  isDisabled = false,
  onQueryChange,
  onSearch,
}: MemoryPanelProps) => {
  return (
    <div className="panel memory">
      <div className="panel-header">
        <h2>Memory search</h2>
        <span className="signal-chip">Search</span>
      </div>
      <div className="search-row">
        <input
          type="text"
          placeholder="Search lab abnormalities"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          aria-label="Search memory"
          disabled={isLoading || isDisabled}
        />
        <button className="secondary-button" type="button" onClick={onSearch} disabled={isLoading || isDisabled}>
          {isLoading ? 'Searching...' : 'Search'}
        </button>
      </div>
      <div className="memory-results">
        {isDisabled ? (
          <div className="empty-state">Select a patient to search memory.</div>
        ) : isLoading ? (
          <>
            <div className="skeleton-row" />
            <div className="skeleton-row" />
          </>
        ) : results.length === 0 ? (
          <div className="empty-state">
            {query.trim() ? 'No matches yet.' : 'Search for a condition, medication, or lab.'}
          </div>
        ) : (
          results.map((result) => (
            <div key={result.chunk_id}>
              <strong>{result.source_type}</strong>
              <p>{result.content}</p>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default MemoryPanel;
