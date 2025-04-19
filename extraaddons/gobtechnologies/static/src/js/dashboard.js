/** @odoo-module **/
import { registry } from '@web/core/registry';
import { loadJS } from '@web/core/assets';
import { Component, onWillStart, onMounted, useRef, useState } from '@odoo/owl';
import { useService } from "@web/core/utils/hooks";

export class PaymentDashboard extends Component {
    setup() {
        this.state = useState({
            complianceStats: {
                total_payments: 0,
                underpaid_count: 0,
                overpaid_count: 0
            }
        });
        
        this.paymentStatusRef = useRef('paymentStatusPie');
        this.collectionTrendsRef = useRef('collectionTrends');
        this.planDistributionRef = useRef('planDistribution');
        this.outstandingByDurationRef = useRef('outstandingByDuration');
        this.rpc = useService("rpc");
        
        onWillStart(async () => {
            await loadJS("https://cdn.jsdelivr.net/npm/chart.js");
            await this.loadDashboardData();
        });
        
        onMounted(() => {
            this.renderCharts();
        });
    }

    async loadDashboardData() {
        const data = await this.rpc("/web/dataset/call_kw/repayment/get_dashboard_data", {
            model: 'repayment',
            method: 'get_dashboard_data',
            args: [],
            kwargs: {},
        });
        this.dashboardData = data;
        this.state.complianceStats = data.compliance_stats;
    }

    renderCharts() {
        // Payment Status Pie Chart
        new Chart(this.paymentStatusRef.el.getContext('2d'), {
            type: 'pie',
            data: {
                labels: ['Fully Paid', 'Underpaid'],
                datasets: [{
                    data: [
                        this.dashboardData.payment_status.fully_paid,
                        this.dashboardData.payment_status.underpaid
                    ],
                    backgroundColor: ['#28a745', '#dc3545']
                }]
            }
        });

        // Collection Trends Line Chart
        new Chart(this.collectionTrendsRef.el.getContext('2d'), {
            type: 'line',
            data: {
                labels: this.dashboardData.collections.months,
                datasets: [{
                    label: 'Expected Collections',
                    data: this.dashboardData.collections.expected,
                    borderColor: '#007bff'
                }, {
                    label: 'Actual Collections',
                    data: this.dashboardData.collections.actual,
                    borderColor: '#28a745'
                }]
            },
            options: {
                scales: {
                    y: { beginAtZero: true }
                }
            }
        });

        // Payment Plan Distribution
        new Chart(this.planDistributionRef.el.getContext('2d'), {
            type: 'bar',
            data: {
                labels: this.dashboardData.plan_distribution.labels,
                datasets: [{
                    label: 'Number of Customers',
                    data: this.dashboardData.plan_distribution.data,
                    backgroundColor: '#17a2b8'
                }]
            },
            options: {
                scales: {
                    y: { beginAtZero: true }
                }
            }
        });

        // Outstanding by Duration
        new Chart(this.outstandingByDurationRef.el.getContext('2d'), {
            type: 'bar',
            data: {
                labels: this.dashboardData.outstanding_by_duration.labels,
                datasets: [{
                    label: 'Outstanding Amount',
                    data: this.dashboardData.outstanding_by_duration.amounts,
                    backgroundColor: '#fd7e14',
                    yAxisID: 'y'
                }, {
                    label: 'Number of Loans',
                    data: this.dashboardData.outstanding_by_duration.counts,
                    backgroundColor: '#20c997',
                    yAxisID: 'y1'
                }]
            },
            options: {
                scales: {
                    y: {
                        beginAtZero: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: 'Amount'
                        }
                    },
                    y1: {
                        beginAtZero: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: 'Count'
                        },
                        grid: {
                            drawOnChartArea: false
                        }
                    }
                }
            }
        });
    }
}

PaymentDashboard.template = 'gobtechnologies.PaymentDashboard';

registry.category('actions').add('gobtechnologies.payment_dashboard', PaymentDashboard);


