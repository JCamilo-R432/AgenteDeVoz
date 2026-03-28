module.exports = {
  apps: [{
    name: 'agentevoz-api',
    script: 'launcher.py',
    cwd: '/opt/AgenteDeVoz',
    instances: 2,
    exec_mode: 'cluster',
    autorestart: true,
    watch: false,
    max_memory_restart: '500M',
    env: {
      PYTHONUNBUFFERED: '1'
    },
    error_file: '/opt/AgenteDeVoz/logs/pm2-error.log',
    out_file: '/opt/AgenteDeVoz/logs/pm2-out.log',
    log_file: '/opt/AgenteDeVoz/logs/pm2-combined.log',
    time: true
  }]
}
