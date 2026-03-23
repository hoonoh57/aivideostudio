    def _request_thumbnails(self, cw):
        """Request thumbnail extraction using QThread (proven pattern)."""
        if cw._thumb_requested:
            return
        cw._thumb_requested = True
        path = cw.clip_data.get("path", "")
        if not path:
            return
        ext = Path(path).suffix.lower()
        image_exts = (".png", ".jpg", ".jpeg", ".bmp", ".gif",
                      ".tiff", ".tif", ".webp", ".svg")
        if ext in image_exts:
            from PyQt6.QtGui import QPixmap
            px = QPixmap(str(path))
            if not px.isNull():
                cw.set_thumbnails(px, px)
                logger.info(f"Thumbnail (image): {Path(path).name}")
            return
        in_pt = cw.clip_data.get("in_point", 0.0)
        out_pt = cw.clip_data.get("out_point",
                    in_pt + cw.clip_data.get("duration", 1.0))
        ff = self._ffmpeg_path or "ffmpeg"
        clip_id = getattr(cw, '_clip_id', -1)
        logger.info(f"Thumbnail request: {Path(path).name} id={clip_id}")
        worker = ThumbnailWorkerThread(clip_id, path, in_pt, out_pt, ff)
        worker.thumbnails_ready.connect(self._on_thumbnails_ready)
        if not hasattr(self, '_thumb_workers'):
            self._thumb_workers = []
        self._thumb_workers.append(worker)
        worker.finished.connect(lambda w=worker: self._thumb_workers.remove(w) if w in self._thumb_workers else None)
        worker.start()

    def _on_thumbnails_ready(self, clip_id, start_path, end_path):
        """Slot on main thread: create QPixmap and assign to clip."""
        from PyQt6.QtGui import QPixmap
        px_start = QPixmap(start_path) if start_path else None
        px_end = QPixmap(end_path) if end_path else None
        if px_start and px_start.isNull():
            px_start = None
        if px_end and px_end.isNull():
            px_end = None
        for track in self.tracks:
            for cw in track["clips"]:
                try:
                    if not cw._alive:
                        continue
                except RuntimeError:
                    continue
                if getattr(cw, '_clip_id', -1) == clip_id:
                    cw.set_thumbnails(px_start, px_end)
                    logger.info(f"Thumbnails loaded: {cw.clip_data.get('name','?')} start={'OK' if px_start else 'None'} end={'OK' if px_end else 'None'}")
                    return

