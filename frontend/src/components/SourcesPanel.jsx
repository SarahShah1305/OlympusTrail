import { sources } from "../sources";

export default function SourcesPanel() {
  return (
    <details className="sources-panel">
      <summary>
        Sources and caveats <span aria-hidden="true">+</span>
      </summary>
      <ul>
        {sources.map((source) => (
          <li key={source.id}>
            <strong>{source.name}</strong>
            <span>{source.organization}</span>
            <p>{source.note}</p>
            <div className="source-links">
              <a href={source.url} target="_blank" rel="noreferrer">
                Source
              </a>
              {source.downloadUrl && (
                <a href={source.downloadUrl} target="_blank" rel="noreferrer">
                  {source.downloadLabel || "Download"}
                </a>
              )}
              {source.archiveUrl && (
                <a href={source.archiveUrl} target="_blank" rel="noreferrer">
                  {source.archiveLabel || "Archive"}
                </a>
              )}
            </div>
          </li>
        ))}
      </ul>
    </details>
  );
}
