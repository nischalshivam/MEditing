'use strict';

const fs = require('fs');
const fsp = fs.promises;
const path = require('path');
const crypto = require('crypto');
const { renderProject } = require('./renderer');

function id() { return 'r_' + crypto.randomUUID().replaceAll('-', '').slice(0, 16); }
function now() { return new Date().toISOString(); }

class RenderQueue {
  constructor(options) {
    this.file = path.join(options.dataDir, 'render-queue.json');
    this.loadProject = options.loadProject; this.projectDir = options.projectDir;
    this.state = { version: 1, active: false, jobs: [] }; this.worker = null;
  }
  async init() {
    try { this.state = JSON.parse(await fsp.readFile(this.file, 'utf8')); } catch {}
    this.state.version = 1; this.state.active = false; this.state.jobs = Array.isArray(this.state.jobs) ? this.state.jobs : [];
    for (const job of this.state.jobs) if (job.status === 'running') { job.status = 'waiting'; job.stage = 'Recovered after app restart'; job.progress = Math.min(.98, Number(job.progress) || 0); }
    await this.save(); return this;
  }
  async save() {
    await fsp.mkdir(path.dirname(this.file), { recursive: true }); const temp = `${this.file}.${process.pid}.tmp`;
    await fsp.writeFile(temp, JSON.stringify(this.state, null, 2), 'utf8'); await fsp.rename(temp, this.file);
  }
  publicState() {
    return { version: this.state.version, active: this.state.active, jobs: this.state.jobs.map(({ cancelRequested, ...job }) => job) };
  }
  async add(project, options = {}) {
    const job = {
      id: id(), projectId: project.id, projectName: project.name, createdAt: now(), updatedAt: now(),
      status: 'waiting', progress: 0, stage: 'Waiting in queue', resolution: options.resolution === '4k' ? '4k' : '1080p',
      quality: ['fast', 'balanced', 'quality'].includes(options.quality) ? options.quality : 'balanced',
      preview: !!options.preview, previewStart: Math.max(0, Number(options.previewStart) || 0), previewDuration: Math.max(3, Math.min(30, Number(options.previewDuration) || 12)),
      output: null, outputName: null, error: null, cancelRequested: false
    };
    this.state.jobs.unshift(job); await this.save(); return job;
  }
  async start() { this.state.active = true; await this.save(); this.kick(); }
  async pause() { this.state.active = false; await this.save(); }
  async retry(jobId) {
    const job = this.state.jobs.find(j => j.id === jobId); if (!job) throw Object.assign(new Error('Render job not found'), { status: 404 });
    if (!['failed', 'canceled', 'complete'].includes(job.status)) return job;
    job.status = 'waiting'; job.progress = 0; job.stage = 'Waiting to retry'; job.error = null; job.output = null; job.outputName = null; job.cancelRequested = false; job.updatedAt = now(); await this.save(); return job;
  }
  async cancel(jobId) {
    const job = this.state.jobs.find(j => j.id === jobId); if (!job) throw Object.assign(new Error('Render job not found'), { status: 404 });
    if (job.status === 'running') { job.cancelRequested = true; job.stage = 'Canceling…'; }
    else if (job.status === 'waiting') { job.status = 'canceled'; job.stage = 'Canceled'; }
    job.updatedAt = now(); await this.save(); return job;
  }
  kick() { if (!this.worker) this.worker = this.run().finally(() => { this.worker = null; if (this.state.active && this.state.jobs.some(j => j.status === 'waiting')) this.kick(); }); }
  async run() {
    while (this.state.active) {
      const job = [...this.state.jobs].reverse().find(j => j.status === 'waiting'); if (!job) { this.state.active = false; await this.save(); return; }
      job.status = 'running'; job.stage = 'Preparing project'; job.startedAt = now(); job.updatedAt = now(); job.cancelRequested = false; await this.save();
      try {
        const project = await this.loadProject(job.projectId); const plan = project.automation?.plan;
        if (!plan?.shots?.length) throw new Error('Automation plan is missing. Open Automate and generate a plan first.');
        const manifest = await renderProject({
          project, projectDir: this.projectDir(project.id), jobId: job.id, plan, resolution: job.resolution, quality: job.quality,
          preview: job.preview, previewStart: job.previewStart, previewDuration: job.previewDuration,
          shouldCancel: () => !!job.cancelRequested,
          onProgress: async (progress, stage) => { job.progress = Math.max(job.progress || 0, Math.min(1, Number(progress) || 0)); job.stage = stage; job.updatedAt = now(); if (!job._lastSave || Date.now() - job._lastSave > 500) { job._lastSave = Date.now(); await this.save().catch(() => {}); } }
        });
        delete job._lastSave; job.status = 'complete'; job.progress = 1; job.stage = 'Complete'; job.output = manifest.output; job.outputName = manifest.outputName; job.completedAt = now(); job.updatedAt = now();
      } catch (error) {
        delete job._lastSave; job.status = error.canceled || job.cancelRequested ? 'canceled' : 'failed'; job.stage = job.status === 'canceled' ? 'Canceled' : 'Failed'; job.error = error.message || String(error); job.updatedAt = now();
      }
      await this.save();
    }
  }
}

module.exports = { RenderQueue };
