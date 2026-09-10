"use client";

import React, { useState, useMemo } from 'react';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ChartAnalysis } from '@/types';

interface ChartDisplayProps {
  chartData: ChartAnalysis;
  className?: string;
  interactive?: boolean;
  showControls?: boolean;
}

const COLORS = ['#8884d8', '#82ca9d', '#ffc658', '#ff7c7c', '#8dd1e1', '#d084d0'];

export function ChartDisplay({
  chartData,
  className,
  interactive = true,
  showControls = true
}: ChartDisplayProps) {
  const [chartType, setChartType] = useState(chartData.chart_type);
  const [selectedElement, setSelectedElement] = useState<any>(null);

  const processedData = useMemo(() => {
    // Convert chart elements to chart data format
    const dataPoints = chartData.data_points || [];

    if (chartType === 'pie_chart') {
      return dataPoints.map((point, index) => ({
        name: point.label || `Item ${index + 1}`,
        value: point.value,
        fill: COLORS[index % COLORS.length]
      }));
    }

    // For other chart types, group by x-axis
    const groupedData = dataPoints.reduce((acc, point) => {
      const key = point.x || point.label || 'default';
      if (!acc[key]) {
        acc[key] = { name: key };
      }
      acc[key][`value_${point.y || 0}`] = point.value;
      return acc;
    }, {} as any);

    return Object.values(groupedData);
  }, [chartData.data_points, chartType]);

  const renderChart = () => {
    const commonProps = {
      data: processedData,
      margin: { top: 5, right: 30, left: 20, bottom: 5 }
    };

    switch (chartType) {
      case 'bar_chart':
        return (
          <BarChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Legend />
            {Object.keys(processedData[0] || {}).filter(key => key.startsWith('value_')).map((key, index) => (
              <Bar key={key} dataKey={key} fill={COLORS[index % COLORS.length]} />
            ))}
          </BarChart>
        );

      case 'line_chart':
        return (
          <LineChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Legend />
            {Object.keys(processedData[0] || {}).filter(key => key.startsWith('value_')).map((key, index) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={COLORS[index % COLORS.length]}
                strokeWidth={2}
              />
            ))}
          </LineChart>
        );

      case 'area_chart':
        return (
          <AreaChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Legend />
            {Object.keys(processedData[0] || {}).filter(key => key.startsWith('value_')).map((key, index) => (
              <Area
                key={key}
                type="monotone"
                dataKey={key}
                stackId="1"
                stroke={COLORS[index % COLORS.length]}
                fill={COLORS[index % COLORS.length]}
              />
            ))}
          </AreaChart>
        );

      case 'pie_chart':
        return (
          <PieChart width={400} height={400}>
            <Pie
              data={processedData}
              cx={200}
              cy={200}
              labelLine={false}
              label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
              outerRadius={80}
              fill="#8884d8"
              dataKey="value"
            >
              {processedData.map((entry: any, index: number) => (
                <Cell key={`cell-${index}`} fill={entry.fill} />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        );

      case 'scatter_plot':
        return (
          <ScatterChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="x" type="number" />
            <YAxis dataKey="y" type="number" />
            <Tooltip cursor={{ strokeDasharray: '3 3' }} />
            <Scatter name="Data Points" data={processedData} fill="#8884d8" />
          </ScatterChart>
        );

      default:
        return (
          <div className="flex items-center justify-center h-64 text-muted-foreground">
            <p>Unsupported chart type: {chartType}</p>
          </div>
        );
    }
  };

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">Chart Analysis</CardTitle>
          {showControls && (
            <div className="flex gap-2">
              <Button
                variant={chartType === 'bar_chart' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setChartType('bar_chart')}
              >
                Bar
              </Button>
              <Button
                variant={chartType === 'line_chart' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setChartType('line_chart')}
              >
                Line
              </Button>
              <Button
                variant={chartType === 'area_chart' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setChartType('area_chart')}
              >
                Area
              </Button>
              <Button
                variant={chartType === 'pie_chart' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setChartType('pie_chart')}
              >
                Pie
              </Button>
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            {renderChart()}
          </ResponsiveContainer>
        </div>

        {chartData.elements && chartData.elements.length > 0 && (
          <div className="mt-4">
            <h4 className="text-sm font-semibold mb-2">Chart Elements</h4>
            <div className="grid grid-cols-2 gap-2 text-xs">
              {chartData.elements.slice(0, 8).map((element, index) => (
                <div
                  key={index}
                  className={`p-2 rounded border cursor-pointer transition-colors ${
                    selectedElement === element
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                  onClick={() => setSelectedElement(element)}
                >
                  <div className="font-medium">{element.type}</div>
                  {element.text && (
                    <div className="text-gray-600 truncate">{element.text}</div>
                  )}
                  {element.value !== undefined && (
                    <div className="text-blue-600 font-semibold">{element.value}</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {chartData.reasoning && chartData.reasoning.length > 0 && (
          <div className="mt-4">
            <h4 className="text-sm font-semibold mb-2">AI Analysis</h4>
            <ul className="text-xs text-gray-600 space-y-1">
              {chartData.reasoning.map((reason, index) => (
                <li key={index} className="flex items-start gap-2">
                  <span className="text-blue-500 mt-1">•</span>
                  <span>{reason}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}







