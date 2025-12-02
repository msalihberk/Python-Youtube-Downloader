try:
    import pyi_splash
    pyi_splash.close()
except:
    pass

import sys
import os
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QComboBox, QListWidget, QProgressBar, QMessageBox, QSplitter
)
from PySide6.QtCore import Qt, QThread, Signal, Slot
import qdarkstyle
from pytubefix import YouTube, Playlist

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class VideoDownloadThread(QThread):
    progress = Signal(int)
    finished = Signal(str)
    error = Signal(str)
    sizeInfo = Signal(int, int)  # (downloaded, total)

    def __init__(self, url, resolution, output_path):
        super().__init__()
        self.url = url
        self.resolution = resolution
        self.output_path = output_path

    def run(self):
        try:
            yt = YouTube(self.url, on_progress_callback=self.on_progress)
            ys = yt.streams.filter(res=self.resolution).first()
            if ys:
                self._filesize = ys.filesize
                ys.download(output_path=self.output_path)
                self.finished.emit(yt.title)
            else:
                self.error.emit(f"Resolution {self.resolution} not available!")
        except Exception as e:
            self.error.emit(str(e))

    def on_progress(self, stream, chunk, bytes_remaining):
        filesize = stream.filesize
        bytes_received = filesize - bytes_remaining
        percent = int((bytes_received / filesize) * 100)
        self.progress.emit(percent)
        self.sizeInfo.emit(bytes_received, filesize)

class PlaylistDownloadThread(QThread):
    progress = Signal(int)
    finished = Signal(str)
    error = Signal(str)
    videoChanged = Signal(str)
    sizeInfo = Signal(int, int, int, int)  # (downloaded, total, playlist_total, playlist_downloaded)

    def __init__(self, video_urls, resolution, output_path):
        super().__init__()
        self.video_urls = video_urls
        self.resolution = resolution
        self.output_path = output_path

    def run(self):
        try:
            self.playlist_total = 0
            self.downloaded_total = 0
            self.filesizes = []
            # Önce tüm dosya boyutlarını topla
            for url in self.video_urls:
                yt = YouTube(url)
                ys = yt.streams.filter(res=self.resolution).first()
                if ys:
                    self.filesizes.append(ys.filesize)
                    self.playlist_total += ys.filesize
                else:
                    self.filesizes.append(0)
            for idx, url in enumerate(self.video_urls):
                yt = YouTube(url, on_progress_callback=self.on_progress)
                ys = yt.streams.filter(res=self.resolution).first()
                if ys:
                    self.videoChanged.emit(yt.title)
                    self._current_filesize = ys.filesize
                    self._current_downloaded = 0
                    self._current_idx = idx
                    ys.download(output_path=self.output_path)
                    self.downloaded_total += ys.filesize
                else:
                    self.error.emit(f"Resolution {self.resolution} not available for {yt.title}!")
                self.progress.emit(int((idx+1)/len(self.video_urls)*100))
            self.finished.emit("Playlist Download Complete!")
        except Exception as e:
            self.error.emit(str(e))

    def on_progress(self, stream, chunk, bytes_remaining):
        filesize = stream.filesize
        bytes_received = filesize - bytes_remaining
        percent = int((bytes_received / filesize) * 100)
        self.progress.emit(percent)
    
        playlist_downloaded = self.downloaded_total + bytes_received
        self.sizeInfo.emit(bytes_received, filesize, self.playlist_total, playlist_downloaded)

class GetVideosThread(QThread):
    videoFound = Signal(str, str)  # title, url
    countChanged = Signal(int)
    finished = Signal(int)
    error = Signal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            playlist = Playlist(self.url)
            count = 0
            for video_url in playlist.video_urls:
                yt = YouTube(video_url)
                self.videoFound.emit(yt.title, video_url)
                count += 1
                self.countChanged.emit(count)
            self.finished.emit(count)
        except Exception as e:
            self.error.emit(str(e))

class DownloaderUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Downloader")
        self.setMinimumSize(900, 520)
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            from PySide6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))
        self.initUI()

    def initUI(self):
        mainLayout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        mainLayout.addWidget(splitter)

        # Playlist Frame
        playlistWidget = QWidget()
        playlistLayout = QVBoxLayout(playlistWidget)
        playlistLabel = QLabel("Playlist Downloader")
        playlistLabel.setStyleSheet("font-weight: bold; font-size: 22px; color: #00e676;")
        playlistLayout.addWidget(playlistLabel)
        self.playlistEntry = QLineEdit()
        self.playlistEntry.setPlaceholderText("Playlist URL")
        self.playlistEntry.setStyleSheet("padding: 8px; border-radius: 8px; font-size: 15px;")
        playlistLayout.addWidget(self.playlistEntry)
        self.getVideosBtn = QPushButton("Get Videos")
        self.getVideosBtn.setStyleSheet("padding: 8px; border-radius: 8px; font-weight: bold; background-color: #00e676; color: #23272f;")
        self.getVideosBtn.clicked.connect(self.getVideos)
        playlistLayout.addWidget(self.getVideosBtn)
        self.comboPL = QComboBox()
        self.comboPL.addItems(["144p", "360p", "720p"])
        self.comboPL.setCurrentIndex(-1)
        self.comboPL.setStyleSheet("padding: 6px; border-radius: 8px; font-size: 14px;")
        playlistLayout.addWidget(self.comboPL)
        self.locationPLBtn = QPushButton("Select Location")
        self.locationPLBtn.setStyleSheet("padding: 8px; border-radius: 8px; font-weight: bold; background-color: #00e676; color: #23272f;")
        self.locationPLBtn.clicked.connect(self.selectLocationPL)
        playlistLayout.addWidget(self.locationPLBtn)
        self.listWidgetPL = QListWidget()
        self.listWidgetPL.setSelectionMode(QListWidget.ExtendedSelection)
        self.listWidgetPL.setStyleSheet("border-radius: 8px; font-size: 14px; background: #23272f; color: #f5f6fa;")
        playlistLayout.addWidget(self.listWidgetPL)
        self.delPLBtn = QPushButton("Delete Selected")
        self.delPLBtn.setStyleSheet("padding: 8px; border-radius: 8px; font-weight: bold; background-color: #e74c3c; color: #fff;")
        self.delPLBtn.clicked.connect(self.deleteSelectedPL)
        playlistLayout.addWidget(self.delPLBtn)
        self.downloadPLBtn = QPushButton("Download Playlist")
        self.downloadPLBtn.setStyleSheet("padding: 8px; border-radius: 8px; font-weight: bold; background-color: #00e676; color: #23272f;")
        self.downloadPLBtn.clicked.connect(self.downloadPlaylist)
        playlistLayout.addWidget(self.downloadPLBtn)
        self.videoNamePL = QLabel("")
        self.videoNamePL.setStyleSheet("font-size: 13px; color: #00e676;")
        playlistLayout.addWidget(self.videoNamePL)
        self.progressPL = QProgressBar()
        self.progressPL.setStyleSheet("QProgressBar {border-radius: 8px; text-align: center;} QProgressBar::chunk {background-color: #00e676; border-radius: 8px;}")
        playlistLayout.addWidget(self.progressPL)
        self.statusLabel = QLabel("")
        self.statusLabel.setStyleSheet("font-size: 13px; color: #f5f6fa;")
        playlistLayout.addWidget(self.statusLabel)
        self.sizeLabelPL = QLabel("")
        self.sizeLabelPL.setStyleSheet("font-size: 13px; color: #f5f6fa;")
        playlistLayout.addWidget(self.sizeLabelPL)
        splitter.addWidget(playlistWidget)

        # Video Frame
        videoWidget = QWidget()
        videoLayout = QVBoxLayout(videoWidget)
        videoLabel = QLabel("Video Downloader")
        videoLabel.setStyleSheet("font-weight: bold; font-size: 22px; color: #00bcd4;")
        videoLayout.addWidget(videoLabel)
        self.videoEntry = QLineEdit()
        self.videoEntry.setPlaceholderText("Video URL")
        self.videoEntry.setStyleSheet("padding: 8px; border-radius: 8px; font-size: 15px;")
        videoLayout.addWidget(self.videoEntry)
        self.comboV = QComboBox()
        self.comboV.addItems(["144p", "360p", "720p"])
        self.comboV.setCurrentIndex(-1)
        self.comboV.setStyleSheet("padding: 6px; border-radius: 8px; font-size: 14px;")
        videoLayout.addWidget(self.comboV)
        self.locationVBtn = QPushButton("Select Location")
        self.locationVBtn.setStyleSheet("padding: 8px; border-radius: 8px; font-weight: bold; background-color: #00bcd4; color: #23272f;")
        self.locationVBtn.clicked.connect(self.selectLocationV)
        videoLayout.addWidget(self.locationVBtn)
        self.videoName = QLabel("")
        self.videoName.setStyleSheet("font-size: 13px; color: #00bcd4;")
        videoLayout.addWidget(self.videoName)
        self.downloadVBtn = QPushButton("Download Video")
        self.downloadVBtn.setStyleSheet("padding: 8px; border-radius: 8px; font-weight: bold; background-color: #00bcd4; color: #23272f;")
        self.downloadVBtn.clicked.connect(self.downloadVideo)
        videoLayout.addWidget(self.downloadVBtn)
        self.progressV = QProgressBar()
        self.progressV.setStyleSheet("QProgressBar {border-radius: 8px; text-align: center;} QProgressBar::chunk {background-color: #00bcd4; border-radius: 8px;}")
        videoLayout.addWidget(self.progressV)
        self.sizeLabelV = QLabel("")
        self.sizeLabelV.setStyleSheet("font-size: 13px; color: #f5f6fa;")
        videoLayout.addWidget(self.sizeLabelV)
        splitter.addWidget(videoWidget)

        self.locationV = ""
        self.locationPL = ""
        self.playlist_urls = []

    def selectLocationV(self):
        self.locationV = QFileDialog.getExistingDirectory(self, "Select Download Location")
        if self.locationV:
            self.locationVBtn.setText(self.locationV)

    def selectLocationPL(self):
        self.locationPL = QFileDialog.getExistingDirectory(self, "Select Download Location")
        if self.locationPL:
            self.locationPLBtn.setText(self.locationPL)

    def getVideos(self):
        url = self.playlistEntry.text().strip()
        if not url:
            QMessageBox.warning(self, "Warning", "Please enter a playlist URL!")
            return
        self.listWidgetPL.clear()
        self.playlist_urls = []
        self.statusLabel.setText("Getting videos...")
        self.getVideosThread = GetVideosThread(url)
        self.getVideosThread.videoFound.connect(self.addVideoToList)
        self.getVideosThread.countChanged.connect(lambda count: self.statusLabel.setText(f"Found: {count}"))
        self.getVideosThread.finished.connect(lambda count: self.statusLabel.setText(f"Total videos: {count}"))
        self.getVideosThread.error.connect(lambda msg: QMessageBox.critical(self, "Error", f"Please Try Again Later\n{msg}"))
        self.getVideosThread.start()

    @Slot(str, str)
    def addVideoToList(self, title, url):
        self.listWidgetPL.addItem(title)
        self.playlist_urls.append(url)

    def deleteSelectedPL(self):
        selected_items = self.listWidgetPL.selectedIndexes()
        if not selected_items:
            return
        for index in sorted(selected_items, key=lambda x: x.row(), reverse=True):
            self.listWidgetPL.takeItem(index.row())
            del self.playlist_urls[index.row()]

    def downloadVideo(self):
        url = self.videoEntry.text().strip()
        res = self.comboV.currentText()
        if not url:
            QMessageBox.warning(self, "Warning", "Please enter a video URL!")
            return
        if res not in ["144p", "360p", "720p"]:
            QMessageBox.warning(self, "Warning", "Please select a resolution!")
            return
        if not self.locationV:
            QMessageBox.warning(self, "Warning", "Please select a download location!")
            return
        self.progressV.setValue(0)
        self.downloadThread = VideoDownloadThread(url, res, self.locationV)
        self.downloadThread.progress.connect(self.progressV.setValue)
        self.downloadThread.finished.connect(lambda title: self.videoName.setText(f"Downloaded: {title}"))
        self.downloadThread.error.connect(lambda msg: QMessageBox.critical(self, "Error", msg))
        self.downloadThread.sizeInfo.connect(self.updateVideoSizeInfo)
        self.downloadThread.start()

    @Slot(int, int)
    def updateVideoSizeInfo(self, downloaded, total):
        self.sizeLabelV.setText(f"Downloaded: {self.format_size(downloaded)} / {self.format_size(total)}")

    def downloadPlaylist(self):
        res = self.comboPL.currentText()
        if not self.playlist_urls:
            QMessageBox.warning(self, "Warning", "Please get playlist videos first!")
            return
        if res not in ["144p", "360p", "720p"]:
            QMessageBox.warning(self, "Warning", "Please select a resolution!")
            return
        if not self.locationPL:
            QMessageBox.warning(self, "Warning", "Please select a download location!")
            return
        self.progressPL.setValue(0)
        self.videoNamePL.setText("")
        self.downloadPLThread = PlaylistDownloadThread(self.playlist_urls, res, self.locationPL)
        self.downloadPLThread.progress.connect(self.progressPL.setValue)
        self.downloadPLThread.finished.connect(lambda msg: QMessageBox.information(self, "Complete", msg))
        self.downloadPLThread.error.connect(lambda msg: QMessageBox.critical(self, "Error", msg))
        self.downloadPLThread.videoChanged.connect(self.updateCurrentPlaylistVideo)
        self.downloadPLThread.sizeInfo.connect(self.updatePlaylistSizeInfo)
        self.downloadPLThread.start()

    @Slot(str)
    def updateCurrentPlaylistVideo(self, title):
        self.videoNamePL.setText(f"Downloading: {title}")

    @Slot(int, int, int, int)
    def updatePlaylistSizeInfo(self, downloaded, total, playlist_total, playlist_downloaded):
        self.sizeLabelPL.setText(f"Current: {self.format_size(downloaded)} / {self.format_size(total)} | Playlist: {self.format_size(playlist_downloaded)} / {self.format_size(playlist_total)}")

    def format_size(self, size):
        # Byte -> MB/GB
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} PB"

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyside6())
    win = DownloaderUI()
    win.show()
    QMessageBox.information(win, "YouTube Downloader", "\nBy Mustafa Salih Berk")
    sys.exit(app.exec())
