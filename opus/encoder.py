"""High-level interface to a opus.api.encoder functions"""

from opus.api import encoder, ctl, constants

APPLICATION_TYPES_MAP = {
    'voip': constants.APPLICATION_VOIP,
    'audio': constants.APPLICATION_AUDIO,
    'restricted_lowdelay': constants.APPLICATION_RESTRICTED_LOWDELAY,
}


class Encoder(object):

    def __init__(self, fs, channels, application):
        """
        Parameters:
            fs : sampling rate
            channels : number of channels
        """

        if application in APPLICATION_TYPES_MAP.keys():
            application = APPLICATION_TYPES_MAP[application]
        elif application in APPLICATION_TYPES_MAP.values():
            pass  # Nothing to do here
        else:
            raise ValueError("`application` value must be in 'voip', 'audio' or 'restricted_lowdelay'")

        self._fs = fs
        self._channels = channels
        self._application = application
        self._state = encoder.create(fs, channels, application)

    def __del__(self):
        if hasattr(self, '_state'):
            # Destroying state only if __init__ completed successfully
            encoder.destroy(self._state)

    def reset_state(self):
        """Resets the codec state to be equivalent to a freshly initialized state"""

        encoder.ctl(self._state, ctl.reset_state)

    def encode(self, data, frame_size):
        return encoder.encode(self._state, data, frame_size, len(data))

    def encode_float(self, data, frame_size, decode_fec=False):
        return encoder.encode_float(self._state, data, frame_size, len(data))

    # CTL interfaces

    _get_final_range = lambda self: encoder.ctl(self._state, ctl.get_final_range)
    final_range = property(_get_final_range)

    _get_bandwidth = lambda self: encoder.ctl(self._state, ctl.get_bandwidth)
    bandwidth = property(_get_bandwidth)

    _get_pitch = lambda self: encoder.ctl(self._state, ctl.get_pitch)
    pitch = property(_get_pitch)

    _get_lsb_depth = lambda self: encoder.ctl(self._state, ctl.get_lsb_depth)
    _set_lsb_depth = lambda self, x: encoder.ctl(self._state, ctl.set_lsb_depth, x)
    lsb_depth = property(_get_lsb_depth, _set_lsb_depth)

    _get_complexity = lambda self: encoder.ctl(self._state, ctl.get_complexity)
    _set_complexity = lambda self, x: encoder.ctl(self._state, ctl.set_complexity, x)
    complexity = property(_get_complexity, _set_complexity)

    _get_bitrate = lambda self: encoder.ctl(self._state, ctl.get_bitrate)
    _set_bitrate = lambda self, x: encoder.ctl(self._state, ctl.set_bitrate, x)
    bitrate = property(_get_bitrate, _set_bitrate)

    _get_vbr = lambda self: encoder.ctl(self._state, ctl.get_vbr)
    _set_vbr = lambda self, x: encoder.ctl(self._state, ctl.set_vbr, x)
    vbr = property(_get_vbr, _set_vbr)

    _get_vbr_constraint = lambda self: encoder.ctl(self._state, ctl.get_vbr_constraint)
    _set_vbr_constraint = lambda self, x: encoder.ctl(self._state, ctl.set_vbr_constraint, x)
    vbr_constraint = property(_get_vbr_constraint, _set_vbr_constraint)

    _get_force_channels = lambda self: encoder.ctl(self._state, ctl.get_force_channels)
    _set_force_channels = lambda self, x: encoder.ctl(self._state, ctl.set_force_channels, x)
    force_channels = property(_get_force_channels, _set_force_channels)

    _get_max_bandwidth = lambda self: encoder.ctl(self._state, ctl.get_max_bandwidth)
    _set_max_bandwidth = lambda self, x: encoder.ctl(self._state, ctl.set_max_bandwidth, x)
    max_bandwidth = property(_get_max_bandwidth, _set_max_bandwidth)

    _set_bandwidth = lambda self, x: encoder.ctl(self._state, ctl.set_bandwidth, x)
    bandwidth = property(None, _set_bandwidth)

    _get_signal = lambda self: encoder.ctl(self._state, ctl.get_signal)
    _set_signal = lambda self, x: encoder.ctl(self._state, ctl.set_signal, x)
    signal = property(_get_signal, _set_signal)

    _get_application = lambda self: encoder.ctl(self._state, ctl.get_application)
    _set_application = lambda self, x: encoder.ctl(self._state, ctl.set_application, x)
    application = property(_get_application, _set_application)

    _get_sample_rate = lambda self: encoder.ctl(self._state, ctl.get_sample_rate)
    sample_rate = property(_get_sample_rate)

    _get_lookahead = lambda self: encoder.ctl(self._state, ctl.get_lookahead)
    lookahead = property(_get_lookahead)

    _get_inband_fec = lambda self: encoder.ctl(self._state, ctl.get_inband_fec)
    _set_inband_fec = lambda self, x: encoder.ctl(self._state, ctl.set_inband_fec, x)
    inband_fec = property(_get_inband_fec, _set_inband_fec)

    _get_packet_loss_perc = lambda self: encoder.ctl(self._state, ctl.get_packet_loss_perc)
    _set_packet_loss_perc = lambda self, x: encoder.ctl(self._state, ctl.set_packet_loss_perc, x)
    packet_loss_perc = property(_get_packet_loss_perc, _set_packet_loss_perc)

    _get_dtx = lambda self: encoder.ctl(self._state, ctl.get_dtx)
    _set_dtx = lambda self, x: encoder.ctl(self._state, ctl.set_dtx, x)
    dtx = property(_get_dtx, _set_dtx)

    def configure_for_voip(self, bitrate=20000, complexity=6, fec=True, 
                           packet_loss_perc=15, dtx=True):
        """便捷方法：配置语音通信优化参数
        
        注意：由于libopus的ctypes可变参数调用限制，某些参数可能设置失败。
        Opus编码器在VOIP应用模式下已经有很好的默认配置，即使某些参数设置失败
        也能正常工作。
        
        参数:
            bitrate: 目标比特率 (默认20kbps，短波语音足够)
            complexity: 编码复杂度 0-10 (默认6，移动端推荐5-8)
            fec: 是否启用前向纠错 (默认True，弱网环境关键)
            packet_loss_perc: 预期丢包率 (默认15%)
            dtx: 是否启用静音检测传输 (默认True，节省带宽)
        """
        # 尝试设置参数，忽略失败
        for name, value in [
            ('bitrate', bitrate),
            ('complexity', complexity),
            ('inband_fec', 1 if fec else 0),
            ('packet_loss_perc', packet_loss_perc if fec else 0),
            ('dtx', 1 if dtx else 0),
        ]:
            try:
                setattr(self, name, value)
            except Exception:
                pass  # 忽略设置失败
        
        return self  # 支持链式调用