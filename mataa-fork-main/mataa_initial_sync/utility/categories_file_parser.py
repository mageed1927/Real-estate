import base64
import pandas as pd
from collections import defaultdict, deque
from io import BytesIO
from odoo.exceptions import UserError


class CategoriesFileParser:
    @staticmethod
    def parse_file(file_name, file_data):
        """Determine the file type and parse accordingly using pandas"""
        if file_name.endswith('.csv'):
            raise UserError("csv parsing is not implemented yet , please convert your files into xlsx format")
        elif file_name.endswith('.xlsx'):
            return CategoriesFileParser._parse_xlsx(file_data)
        else:
            raise UserError("Invalid file format. Please upload a CSV or XLSX file.")

    @staticmethod
    def _parse_xlsx(file_data):
        """Parse XLSX file using pandas and return data"""
        decoded_file_data = base64.b64decode(file_data)
        file_stream = BytesIO(decoded_file_data)

        data_types = {
            'mataa_id': pd.Int64Dtype(),
            'mataa_parent_id': pd.Int64Dtype(),
            'name': str
        }

        df = pd.read_excel(file_stream, engine='openpyxl', dtype=data_types)
        df = df.dropna(how='all').reset_index(drop=True)
        df = df.astype(object).where(df.notna(), None)

        if not isinstance(df, pd.DataFrame):
            raise UserError("Parsed data is not in the expected format.")

        return df

    @staticmethod
    def topological_sort(data):
        # Build the graph from the DataFrame
        graph = defaultdict(list)
        in_degree = defaultdict(int)
        nodes = set()

        for _, row in data.iterrows():
            mataa_id = row['mataa_id']
            mataa_parent_id = row['mataa_parent_id']

            nodes.add(mataa_id)
            if not pd.isna(mataa_parent_id):  # If there's a parent
                graph[mataa_parent_id].append(mataa_id)
                in_degree[mataa_id] += 1
            else:
                in_degree[mataa_id] += 0

        # Detect cycles and prepare cycle path information
        def find_cycle(node, visited, stack):
            visited[node] = True
            stack[node] = True
            for child in graph[node]:
                if not visited[child]:
                    if find_cycle(child, visited, stack):
                        return True
                elif stack[child]:  # Cycle detected
                    cycle_path.append(child)
                    return True
            stack[node] = False
            return False

        # Check for cycles and store cycle path if found
        visited = {node: False for node in nodes}
        stack = {node: False for node in nodes}
        cycle_path = []
        for node in nodes:
            if not visited[node]:
                if find_cycle(node, visited, stack):
                    cycle_path = [node] + cycle_path  # Add starting node to cycle path
                    break

        if cycle_path:
            raise UserError(f"Cycle detected in the category hierarchy: {' -> '.join(map(str, cycle_path))}")

        # Perform topological sort using Kahn’s algorithm if no cycle detected
        queue = deque([node for node in nodes if in_degree[node] == 0])
        sorted_nodes = []

        while queue:
            node = queue.popleft()
            sorted_nodes.append(node)
            for child in graph[node]:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        if len(sorted_nodes) != len(nodes):
            unsorted_nodes = nodes - set(sorted_nodes)
            unsorted_nodes_str = ', '.join(map(str, unsorted_nodes))
            raise UserError(f"Cycle detected in the category hierarchy, cannot proceed with topological sorting. "
                    f"Unsorted nodes: {unsorted_nodes_str}")

        # Reorder the data according to the topological order
        sorted_data = []
        mataa_id_to_row = {row['mataa_id']: row for _, row in data.iterrows()}
        for mataa_id in sorted_nodes:
            sorted_data.append(mataa_id_to_row[mataa_id])

        return sorted_data
