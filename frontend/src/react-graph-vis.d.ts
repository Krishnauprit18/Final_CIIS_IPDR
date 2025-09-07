declare module 'react-graph-vis' {
  import { Component } from 'react';

  export interface Node {
    id: string;
    label?: string;
    color?: any;
    font?: any;
    shape?: string;
  }

  export interface Edge {
    from: string;
    to: string;
    color?: any;
    arrows?: any;
  }

  export interface GraphData {
    nodes: Node[];
    edges: Edge[];
  }

  export interface GraphEvents {
    select?: (params: { nodes: string[]; edges: string[] }) => void;
    click?: (params: any) => void;
  }

  export interface GraphOptions {
    layout?: any;
    edges?: any;
    physics?: any;
    nodes?: any;
    height?: string;
  }

  export interface GraphProps {
    graph: GraphData;
    options?: GraphOptions;
    events?: GraphEvents;
    style?: React.CSSProperties;
  }

  export default class Graph extends Component<GraphProps> {}
}