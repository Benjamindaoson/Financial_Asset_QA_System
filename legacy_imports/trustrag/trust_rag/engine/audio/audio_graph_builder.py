"""
Audio Graph Builder for GraphRAG.

This module builds knowledge graphs from audio content, focusing on
speech transcription and multimodal integration for high-accuracy audio processing.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class AudioGraphBuilder:
    """
    Build knowledge graphs from audio content for GraphRAG.
    """

    def __init__(self, graph_db=None, config: Optional[Dict[str, Any]] = None):
        """
        Initialize audio graph builder.

        Args:
            graph_db: Graph database instance
            config: Configuration for graph building
        """
        self.graph_db = graph_db
        self.config = config or {}

        # Node and edge type prefixes
        self.audio_prefix = "audio"
        self.transcript_prefix = "transcript"
        self.emotion_prefix = "emotion"
        self.feature_prefix = "feature"

        # Relationship types
        self.rel_types = {
            'HAS_TRANSCRIPT': 'HAS_TRANSCRIPT',
            'HAS_EMOTION': 'HAS_EMOTION',
            'HAS_FEATURE': 'HAS_FEATURE',
            'MENTIONS': 'MENTIONS',
            'FEELS': 'FEELS',
            'CHARACTERIZES': 'CHARACTERIZES',
            'TEMPORAL_SEQUENCE': 'TEMPORAL_SEQUENCE'
        }

        logger.info("Audio graph builder initialized")

    def build_audio_graph(
        self,
        audio_processing_result: Dict[str, Any],
        transcription_result: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build knowledge graph from audio transcription results.

        Args:
            audio_processing_result: Result from AudioProcessor
            transcription_result: Result from AudioTranscriber
            metadata: Additional metadata

        Returns:
            Graph building result with node/edge information
        """
        metadata = metadata or {}

        # Create main audio node
        audio_node = self._create_audio_node(audio_processing_result, metadata)

        # Create transcript node
        transcript_node = self._create_transcript_node(transcription_result)

        # Create feature nodes
        feature_nodes = self._create_feature_nodes(audio_processing_result)

        # Create relationships (focused on transcription)
        edges = self._create_audio_relationships(
            audio_node, transcript_node, feature_nodes
        )

        # Extract entities from transcript for additional nodes
        entity_nodes, entity_edges = self._extract_entities_from_transcript(
            transcription_result, audio_node
        )

        # Build complete graph structure
        graph_data = {
            'audio_node': audio_node,
            'transcript_node': transcript_node,
            'feature_nodes': feature_nodes,
            'entity_nodes': entity_nodes,
            'edges': edges + entity_edges,
            'metadata': {
                'build_timestamp': datetime.now().isoformat(),
                'total_nodes': 2 + len(feature_nodes) + len(entity_nodes),
                'total_edges': len(edges) + len(entity_edges)
            }
        }

        # Store in graph database if available
        if self.graph_db:
            self._store_graph_data(graph_data)

        logger.info(f"Built audio graph with {graph_data['metadata']['total_nodes']} nodes and {graph_data['metadata']['total_edges']} edges")

        return graph_data

    def _create_audio_node(
        self,
        processing_result: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create audio content node."""
        node_id = f"{self.audio_prefix}_{uuid.uuid4().hex[:8]}"

        properties = {
            'id': node_id,
            'type': 'audio_content',
            'file_path': processing_result.get('file_path', ''),
            'file_size': processing_result.get('file_size', 0),
            'format': processing_result.get('format', ''),
            'duration': processing_result.get('duration', 0.0),
            'sample_rate': processing_result.get('sample_rate', 0),
            'channels': processing_result.get('channels', 1),
            'processed': processing_result.get('processed', False),
            'truncated': processing_result.get('truncated', False),
            'created_at': datetime.now().isoformat(),
            **metadata
        }

        return {
            'id': node_id,
            'labels': ['Audio', 'Content'],
            'properties': properties
        }

    def _create_transcript_node(self, transcription_result: Dict[str, Any]) -> Dict[str, Any]:
        """Create transcript node."""
        node_id = f"{self.transcript_prefix}_{uuid.uuid4().hex[:8]}"

        properties = {
            'id': node_id,
            'type': 'transcript',
            'text': transcription_result.get('text', ''),
            'confidence': transcription_result.get('confidence', 0.0),
            'language': transcription_result.get('language', 'unknown'),
            'duration': transcription_result.get('duration', 0.0),
            'backend': transcription_result.get('backend', 'unknown'),
            'word_count': len(transcription_result.get('text', '').split()),
            'created_at': datetime.now().isoformat()
        }

        # Add segment information if available
        segments = transcription_result.get('segments', [])
        if segments:
            properties['segments'] = segments
            properties['segment_count'] = len(segments)

        return {
            'id': node_id,
            'labels': ['Transcript', 'Text'],
            'properties': properties
        }


    def _create_feature_nodes(self, processing_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create audio feature nodes."""
        nodes = []
        features = processing_result.get('features', {})

        for feature_name, feature_data in features.items():
            node_id = f"{self.feature_prefix}_{feature_name}_{uuid.uuid4().hex[:6]}"

            properties = {
                'id': node_id,
                'type': 'audio_feature',
                'feature_name': feature_name,
                'feature_data': feature_data,
                'created_at': datetime.now().isoformat()
            }

            # Add specific properties based on feature type
            if feature_name == 'mfccs':
                properties['dimensions'] = len(feature_data.get('mean', []))
            elif feature_name in ['chroma', 'spectral_centroid', 'zero_crossing_rate', 'rms_energy']:
                properties['mean_value'] = feature_data.get('mean', 0)
                properties['std_value'] = feature_data.get('std', 0)
            elif feature_name == 'pitch':
                properties['mean_pitch'] = feature_data.get('mean', 0)
                properties['voiced_ratio'] = feature_data.get('voiced_ratio', 0)
            elif feature_name == 'tempo':
                properties['tempo_bpm'] = feature_data
            elif feature_name == 'onset_strength':
                properties['mean_strength'] = feature_data.get('mean', 0)
                properties['max_strength'] = feature_data.get('max', 0)

            nodes.append({
                'id': node_id,
                'labels': ['AudioFeature', feature_name.title()],
                'properties': properties
            })

        return nodes

    def _create_audio_relationships(
        self,
        audio_node: Dict[str, Any],
        transcript_node: Dict[str, Any],
        feature_nodes: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Create relationships between audio nodes."""
        edges = []

        # Audio -> Transcript
        edges.append({
            'source': audio_node['id'],
            'target': transcript_node['id'],
            'type': self.rel_types['HAS_TRANSCRIPT'],
            'properties': {
                'confidence': transcript_node['properties']['confidence'],
                'created_at': datetime.now().isoformat()
            }
        })

        # Audio -> Features
        for feature_node in feature_nodes:
            edges.append({
                'source': audio_node['id'],
                'target': feature_node['id'],
                'type': self.rel_types['HAS_FEATURE'],
                'properties': {
                    'feature_type': feature_node['properties']['feature_name'],
                    'created_at': datetime.now().isoformat()
                }
            })

        # Transcript -> Features (for audio-text alignment)
        for feature_node in feature_nodes:
            if feature_node['properties']['feature_name'] in ['mfccs', 'chroma']:
                edges.append({
                    'source': transcript_node['id'],
                    'target': feature_node['id'],
                    'type': 'AUDIO_FEATURES',
                    'properties': {
                        'feature_type': feature_node['properties']['feature_name'],
                        'alignment': 'audio_text_sync',
                        'created_at': datetime.now().isoformat()
                    }
                })

        return edges

    def _extract_entities_from_transcript(
        self,
        transcription_result: Dict[str, Any],
        audio_node: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Extract entities from transcript and create nodes/edges."""
        nodes = []
        edges = []

        text = transcription_result.get('text', '')
        if not text:
            return nodes, edges

        # Simple entity extraction (can be enhanced with NER models)
        entities = self._simple_entity_extraction(text)

        for entity_type, entity_list in entities.items():
            for entity_text in entity_list:
                entity_id = f"entity_{entity_type}_{uuid.uuid4().hex[:6]}"

                # Create entity node
                entity_node = {
                    'id': entity_id,
                    'labels': ['Entity', entity_type.title()],
                    'properties': {
                        'type': entity_type,
                        'text': entity_text,
                        'mentioned_in': 'audio_transcript',
                        'confidence': 0.8,  # Simple extraction confidence
                        'created_at': datetime.now().isoformat()
                    }
                }
                nodes.append(entity_node)

                # Create relationship: Audio -> Entity (mentions)
                edges.append({
                    'source': audio_node['id'],
                    'target': entity_id,
                    'type': self.rel_types['MENTIONS'],
                    'properties': {
                        'entity_type': entity_type,
                        'context': 'transcript',
                        'created_at': datetime.now().isoformat()
                    }
                })

                # Create relationship: Transcript -> Entity (mentions)
                transcript_id = f"{self.transcript_prefix}_{uuid.uuid4().hex[:8]}"  # This should match actual transcript node
                # Note: In real implementation, we'd pass the transcript node ID
                edges.append({
                    'source': 'transcript_node_id',  # Placeholder
                    'target': entity_id,
                    'type': self.rel_types['MENTIONS'],
                    'properties': {
                        'entity_type': entity_type,
                        'context': 'text_content',
                        'created_at': datetime.now().isoformat()
                    }
                })

        return nodes, edges

    def _simple_entity_extraction(self, text: str) -> Dict[str, List[str]]:
        """Simple entity extraction from text."""
        entities = {
            'person': [],
            'organization': [],
            'location': [],
            'date': [],
            'number': []
        }

        # Very basic extraction patterns
        import re

        # Person names (simple pattern)
        person_pattern = r'\b[A-Z][a-z]+\s[A-Z][a-z]+\b'
        entities['person'] = re.findall(person_pattern, text)

        # Organizations (simple patterns)
        org_patterns = [
            r'\b[A-Z][a-z]+\s(?:Inc|Corp|LLC|Ltd|Company)\b',
            r'\b[A-Z]{2,}\b'  # Acronyms
        ]
        for pattern in org_patterns:
            entities['organization'].extend(re.findall(pattern, text))

        # Locations (cities, countries - very basic)
        location_pattern = r'\b(?:New York|London|Paris|Tokyo|Beijing|Berlin|Rome|Moscow)\b'
        entities['location'] = re.findall(location_pattern, text)

        # Dates
        date_pattern = r'\b\d{1,2}/\d{1,2}/\d{4}\b|\b\d{4}-\d{2}-\d{2}\b'
        entities['date'] = re.findall(date_pattern, text)

        # Numbers
        number_pattern = r'\b\d+(?:\.\d+)?\b'
        numbers = re.findall(number_pattern, text)
        entities['number'] = numbers[:10]  # Limit to first 10 numbers

        # Remove duplicates
        for entity_type in entities:
            entities[entity_type] = list(set(entities[entity_type]))

        return entities

    def _store_graph_data(self, graph_data: Dict[str, Any]):
        """Store graph data in database."""
        if not self.graph_db:
            return

        try:
            # Store nodes
            nodes_to_store = [
                graph_data['audio_node'],
                graph_data['transcript_node'],
                graph_data['emotion_node']
            ] + graph_data['feature_nodes'] + graph_data['entity_nodes']

            for node in nodes_to_store:
                self.graph_db.create_node(node['labels'], node['properties'])

            # Store edges
            for edge in graph_data['edges']:
                self.graph_db.create_relationship(
                    edge['source'],
                    edge['target'],
                    edge['type'],
                    edge['properties']
                )

            logger.info("Stored audio graph data in database")

        except Exception as e:
            logger.error(f"Failed to store graph data: {e}")

    def query_audio_graph(self, audio_id: str) -> Dict[str, Any]:
        """
        Query audio graph by audio ID.

        Args:
            audio_id: Audio node ID

        Returns:
            Graph query results
        """
        if not self.graph_db:
            return {'error': 'No graph database available'}

        try:
            # Query connected nodes and relationships
            query = f"""
            MATCH (a:Audio {{id: '{audio_id}'}})
            OPTIONAL MATCH (a)-[r1:HAS_TRANSCRIPT]->(t:Transcript)
            OPTIONAL MATCH (a)-[r2:HAS_FEATURE]->(f:AudioFeature)
            OPTIONAL MATCH (a)-[r3:MENTIONS]->(entity:Entity)
            RETURN a, t, collect(f) as features, collect(entity) as entities,
                   collect(r1) as transcript_rels, collect(r2) as feature_rels,
                   collect(r3) as entity_rels
            """

            result = self.graph_db.query(query)

            if result and len(result) > 0:
                return result[0]
            else:
                return {'error': 'Audio not found'}

        except Exception as e:
            logger.error(f"Audio graph query failed: {e}")
            return {'error': str(e)}


    def get_builder_info(self) -> Dict[str, Any]:
        """Get builder information."""
        return {
            'node_prefixes': {
                'audio': self.audio_prefix,
                'transcript': self.transcript_prefix,
                'feature': self.feature_prefix
            },
            'relationship_types': self.rel_types,
            'graph_db_available': self.graph_db is not None,
            'config': self.config
        }
