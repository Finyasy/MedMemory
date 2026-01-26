/**
 * Neural network brain visualization for MedMemory branding
 * Inspired by connected neural pathways representing medical memory
 */

const BrainVisualization = () => {
  // Generate nodes for the brain shape
  const nodes = [
    // Core center nodes (bright)
    { x: 200, y: 150, r: 6, layer: 'core' },
    { x: 185, y: 140, r: 5, layer: 'core' },
    { x: 215, y: 140, r: 5, layer: 'core' },
    { x: 190, y: 165, r: 4, layer: 'core' },
    { x: 210, y: 165, r: 4, layer: 'core' },
    { x: 200, y: 130, r: 4, layer: 'core' },
    
    // Inner ring
    { x: 160, y: 130, r: 4, layer: 'inner' },
    { x: 240, y: 130, r: 4, layer: 'inner' },
    { x: 150, y: 160, r: 3, layer: 'inner' },
    { x: 250, y: 160, r: 3, layer: 'inner' },
    { x: 165, y: 185, r: 4, layer: 'inner' },
    { x: 235, y: 185, r: 4, layer: 'inner' },
    { x: 200, y: 195, r: 3, layer: 'inner' },
    { x: 175, y: 115, r: 3, layer: 'inner' },
    { x: 225, y: 115, r: 3, layer: 'inner' },
    
    // Middle ring
    { x: 130, y: 120, r: 3, layer: 'middle' },
    { x: 270, y: 120, r: 3, layer: 'middle' },
    { x: 120, y: 155, r: 3, layer: 'middle' },
    { x: 280, y: 155, r: 3, layer: 'middle' },
    { x: 135, y: 190, r: 3, layer: 'middle' },
    { x: 265, y: 190, r: 3, layer: 'middle' },
    { x: 155, y: 210, r: 2, layer: 'middle' },
    { x: 245, y: 210, r: 2, layer: 'middle' },
    { x: 200, y: 220, r: 3, layer: 'middle' },
    { x: 145, y: 100, r: 2, layer: 'middle' },
    { x: 255, y: 100, r: 2, layer: 'middle' },
    { x: 200, y: 95, r: 3, layer: 'middle' },
    
    // Outer ring
    { x: 100, y: 130, r: 2, layer: 'outer' },
    { x: 300, y: 130, r: 2, layer: 'outer' },
    { x: 90, y: 165, r: 2, layer: 'outer' },
    { x: 310, y: 165, r: 2, layer: 'outer' },
    { x: 105, y: 195, r: 2, layer: 'outer' },
    { x: 295, y: 195, r: 2, layer: 'outer' },
    { x: 125, y: 215, r: 2, layer: 'outer' },
    { x: 275, y: 215, r: 2, layer: 'outer' },
    { x: 175, y: 235, r: 2, layer: 'outer' },
    { x: 225, y: 235, r: 2, layer: 'outer' },
    { x: 115, y: 95, r: 2, layer: 'outer' },
    { x: 285, y: 95, r: 2, layer: 'outer' },
    { x: 165, y: 80, r: 2, layer: 'outer' },
    { x: 235, y: 80, r: 2, layer: 'outer' },
    
    // Periphery
    { x: 75, y: 145, r: 2, layer: 'periphery' },
    { x: 325, y: 145, r: 2, layer: 'periphery' },
    { x: 85, y: 185, r: 1.5, layer: 'periphery' },
    { x: 315, y: 185, r: 1.5, layer: 'periphery' },
    { x: 140, y: 235, r: 1.5, layer: 'periphery' },
    { x: 260, y: 235, r: 1.5, layer: 'periphery' },
    { x: 200, y: 250, r: 2, layer: 'periphery' },
    { x: 95, y: 210, r: 1.5, layer: 'periphery' },
    { x: 305, y: 210, r: 1.5, layer: 'periphery' },
    { x: 130, y: 75, r: 1.5, layer: 'periphery' },
    { x: 270, y: 75, r: 1.5, layer: 'periphery' },
    { x: 200, y: 65, r: 2, layer: 'periphery' },
  ];

  // Generate connections between nearby nodes
  const connections: Array<{ x1: number; y1: number; x2: number; y2: number; opacity: number }> = [];
  
  nodes.forEach((node1, i) => {
    nodes.forEach((node2, j) => {
      if (i < j) {
        const dist = Math.sqrt(Math.pow(node1.x - node2.x, 2) + Math.pow(node1.y - node2.y, 2));
        if (dist < 55) {
          const opacity = Math.max(0.1, 1 - dist / 60);
          connections.push({
            x1: node1.x,
            y1: node1.y,
            x2: node2.x,
            y2: node2.y,
            opacity,
          });
        }
      }
    });
  });

  const getNodeColor = (layer: string) => {
    switch (layer) {
      case 'core': return 'var(--accent-strong)';
      case 'inner': return 'var(--accent-soft)';
      case 'middle': return 'var(--accent-muted)';
      default: return 'var(--text-muted)';
    }
  };

  const getNodeOpacity = (layer: string) => {
    switch (layer) {
      case 'core': return 1;
      case 'inner': return 0.9;
      case 'middle': return 0.7;
      case 'outer': return 0.5;
      default: return 0.3;
    }
  };

  return (
    <div className="brain-visualization">
      <svg viewBox="0 0 400 300" className="brain-svg" aria-label="MedMemory Neural Network">
        <defs>
          {/* Glow filter for center */}
          <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="8" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          
          {/* Gradient for connections */}
          <linearGradient id="connectionGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="var(--accent-strong)" stopOpacity="0.3" />
            <stop offset="50%" stopColor="var(--accent-soft)" stopOpacity="0.5" />
            <stop offset="100%" stopColor="var(--accent-muted)" stopOpacity="0.3" />
          </linearGradient>

          {/* Radial gradient for center glow */}
          <radialGradient id="centerGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="var(--accent-strong)" stopOpacity="0.4" />
            <stop offset="100%" stopColor="var(--accent-strong)" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* Background glow */}
        <ellipse cx="200" cy="150" rx="80" ry="60" fill="url(#centerGlow)" className="brain-glow" />

        {/* Connections */}
        <g className="brain-connections">
          {connections.map((conn, i) => (
            <line
              key={`conn-${i}`}
              x1={conn.x1}
              y1={conn.y1}
              x2={conn.x2}
              y2={conn.y2}
              stroke="var(--accent-muted)"
              strokeWidth="1"
              opacity={conn.opacity * 0.6}
              className="brain-connection"
            />
          ))}
        </g>

        {/* Nodes */}
        <g className="brain-nodes">
          {nodes.map((node, i) => (
            <circle
              key={`node-${i}`}
              cx={node.x}
              cy={node.y}
              r={node.r}
              fill={getNodeColor(node.layer)}
              opacity={getNodeOpacity(node.layer)}
              className={`brain-node brain-node-${node.layer}`}
              filter={node.layer === 'core' ? 'url(#glow)' : undefined}
            />
          ))}
        </g>

        {/* Animated pulse rings */}
        <circle cx="200" cy="150" r="30" fill="none" stroke="var(--accent-strong)" strokeWidth="1" opacity="0.3" className="pulse-ring pulse-1" />
        <circle cx="200" cy="150" r="50" fill="none" stroke="var(--accent-soft)" strokeWidth="1" opacity="0.2" className="pulse-ring pulse-2" />
        <circle cx="200" cy="150" r="70" fill="none" stroke="var(--accent-muted)" strokeWidth="1" opacity="0.1" className="pulse-ring pulse-3" />
      </svg>
      
      <div className="brain-label">
        <span className="brand-text">Med</span>
        <span className="brand-text accent">Memory</span>
      </div>
    </div>
  );
};

export default BrainVisualization;
