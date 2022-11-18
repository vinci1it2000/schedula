import React from 'react';
import PropTypes from 'prop-types';
import Toolbar from '@mui/material/Toolbar';
import Box from '@mui/material/Box';
import Fade from '@mui/material/Fade';
import useScrollTrigger from '@mui/material/useScrollTrigger';
import Fab from '@mui/material/Fab';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';
import {styled, useTheme} from '@mui/material/styles';
import MuiDrawer from '@mui/material/Drawer';
import MuiAppBar from '@mui/material/AppBar';
import List from '@mui/material/List';
import CssBaseline from '@mui/material/CssBaseline';
import Divider from '@mui/material/Divider';
import IconButton from '@mui/material/IconButton';
import MenuIcon from '@mui/icons-material/Menu';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import ListItemAvatar from '@mui/material/ListItemAvatar';
import Avatar from '@mui/material/Avatar';
import FileDownloadOutlinedIcon from '@mui/icons-material/FileDownloadOutlined';
import FileUploadOutlinedIcon from '@mui/icons-material/FileUploadOutlined';
import PlayCircleIcon from '@mui/icons-material/PlayCircle';
import {exportJson} from './io';
import Tooltip from '@mui/material/Tooltip';
import ReactFullscreen from 'react-easyfullscreen';
import FullscreenIcon from '@mui/icons-material/Fullscreen';
import FullscreenExitIcon from '@mui/icons-material/FullscreenExit';
import screenfull from 'screenfull';
import DataSaverOnIcon from '@mui/icons-material/DataSaverOn';
import DataSaverOffIcon from '@mui/icons-material/DataSaverOff';
import RestoreIcon from '@mui/icons-material/Restore';
import hash from 'object-hash'
import DifferenceIcon from '@mui/icons-material/Difference';
import DialogTitle from '@mui/material/DialogTitle';
import Dialog from '@mui/material/Dialog';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import Button from '@mui/material/Button';
import ReactDiffViewer from 'react-diff-viewer';
import ReplayIcon from '@mui/icons-material/Replay';
import CancelIcon from '@mui/icons-material/Cancel';

function ScrollTop(props) {
    const {children, window, anchor} = props;
    // Note that you normally won't need to set the window ref as useScrollTrigger
    // will default to window.
    // This is only being set here because the demo is in an iframe.
    const trigger = useScrollTrigger({
        target: window ? window() : undefined,
        disableHysteresis: true,
        threshold: 100,
    });

    const handleClick = (event) => {
        anchor.scrollIntoView({
            block: 'center',
        });
    };

    return (
        <Fade in={trigger}>
            <Box
                onClick={handleClick}
                role="presentation"
                sx={{position: 'fixed', bottom: 16, right: 16}}
            >
                {children}
            </Box>
        </Fade>
    );
}

ScrollTop.propTypes = {
    children: PropTypes.element.isRequired,
    /**
     * Injected by the documentation to work in an iframe.
     * You won't need it on your project.
     */
    window: PropTypes.func,
};

function a11yProps(index) {
    return {
        id: `tab-${index}`,
        'aria-controls': `tabpanel-${index}`,
    };
}

const drawerWidth = 240;

const openedMixin = (theme) => ({
    width: drawerWidth,
    transition: theme.transitions.create('width', {
        easing: theme.transitions.easing.sharp,
        duration: theme.transitions.duration.enteringScreen,
    }),
    overflowX: 'hidden'
});

const closedMixin = (theme) => ({
    transition: theme.transitions.create('width', {
        easing: theme.transitions.easing.sharp,
        duration: theme.transitions.duration.leavingScreen,
    }),
    overflowX: 'hidden',
    width: `calc(${theme.spacing(7)} + 1px)`,
    [theme.breakpoints.up('sm')]: {
        width: `calc(${theme.spacing(7)} + 1px)`,
    },
});

const DrawerHeader = styled('div')(({theme}) => ({
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'flex-end',
    padding: theme.spacing(0, 1),
    // necessary for content to be below app bar
    ...theme.mixins.toolbar,
}));

const DrawerAppBar = styled(MuiAppBar, {
    shouldForwardProp: (prop) => prop !== 'open',
})(({theme, open}) => ({
    zIndex: theme.zIndex.drawer + 1,
    transition: theme.transitions.create(['width', 'margin'], {
        easing: theme.transitions.easing.sharp,
        duration: theme.transitions.duration.leavingScreen,
    }),
    ...(open && {
        marginLeft: drawerWidth,
        width: `calc(100% - ${drawerWidth}px)`,
        transition: theme.transitions.create(['width', 'margin'], {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.enteringScreen,
        }),
    }),
}));

const Drawer = styled(MuiDrawer, {shouldForwardProp: (prop) => prop !== 'open'})(
    ({theme, open}) => ({
        width: drawerWidth,
        flexShrink: 0,
        whiteSpace: 'nowrap',
        boxSizing: 'border-box',
        ...(open && {
            ...openedMixin(theme),
            '& .MuiDrawer-paper': openedMixin(theme),
        }),
        ...(!open && {
            ...closedMixin(theme),
            '& .MuiDrawer-paper': closedMixin(theme),
        }),
    }),
);
const appendData = (key, formData) => {
    let dataHash = hash(formData, {
        'algorithm': 'sha1',
        'encoding': 'base64'
    }), storedData = window.sessionStorage.getItem(key) || '[]';

    if (!storedData.endsWith(`,"${dataHash}"]]`)) {

        let data = `${JSON.stringify(formData)}`,
            size = data.length,
            date = `${Math.floor(Date.now() / 60000)}`,
            n = storedData.length - 1;

        storedData = storedData.slice(0, n)
        n -= 32
        if (storedData.slice(0, n).endsWith(date)) {
            n -= date.length + 2
            let v = n + 1
            while (storedData.charAt(n) !== ',') {
                n -= 1
            }
            n -= parseInt(storedData.slice(n + 1, v)) + 2
            storedData = storedData.slice(0, n) || '['
        }

        storedData += `${storedData === '[' ? '' : ','}[${data},${size},${date},"${dataHash}"]]`
        window.sessionStorage.setItem(key, storedData);
    }
}
export default function _nav(props) {
    const [fullScreen, setFullScreen] = React.useState(false);
    const [savingData, setSavingData] = React.useState(true);
    const [value, setValue] = React.useState(props.current_tab || 0);
    const handleChange = (event, newValue) => {
        setValue(newValue);
    };
    const theme = useTheme();
    const [open, setOpen] = React.useState(false);
    let key = 'schedula-' + props.context.props.formContext.$id + '-' + props.context.props.idSchema.$id + '-formData';
    let formData = props.context.props.formData;
    if (savingData) {
        appendData(key, formData)
    }

    const handleDrawerOpen = () => {
        setOpen(true);
    };

    const handleDrawerClose = () => {
        setOpen(false);
    };

    const upload = (event) => {
        event.preventDefault();
        if (event.target.files.length) {
            const reader = new FileReader()
            reader.onload = async ({target}) => {
                props.context.props.onChange(JSON.parse(target.result))
            }
            reader.readAsText(event.target.files[0]);
            event.target.value = null;
        }
    }
    let AppBar = props['disable-drawer'] ? MuiAppBar : DrawerAppBar;
    const [openRestore, setOpenRestore] = React.useState(false);
    const [openDiff, setOpenDiff] = React.useState(false);
    const [oldValue, setOldValue] = React.useState(null);
    const handleDiffClose = () => {
        setOpenDiff(false)
        setOldValue(null)
    }

    let dataHash = null;
    if (openRestore) {
        dataHash = hash(formData, {
            'algorithm': 'sha1',
            'encoding': 'base64'
        })
    }
    const anchor = <div/>
    return (
        <ReactFullscreen onChange={() => {
            setFullScreen(screenfull.isFullscreen)
        }}>
            {({ref, onToggle, isEnabled}) => (
                <Box ref={ref} sx={{display: 'flex'}}>
                    <CssBaseline/>
                    <AppBar color="inherit" position="fixed" open={open}>
                        <Toolbar>
                            {props['disable-drawer'] ? null :
                                <IconButton
                                    color="inherit"
                                    aria-label="open drawer"
                                    onClick={handleDrawerOpen}
                                    edge="start"
                                    sx={{
                                        ...(open && {display: 'none'}),
                                    }}
                                >
                                    <MenuIcon/>
                                </IconButton>}
                            <Box key={0}
                                 sx={{marginLeft: 5}}>{props['children-left']}</Box>
                            {props['disable-tabs'] ? null :
                                <Tabs key={1}
                                      value={value}
                                      onChange={handleChange}
                                      sx={{flexGrow: 1}}
                                      {...props}
                                >
                                    {props.children.map((element, index) => (
                                        <Tab key={index}
                                             label={(element.props.schema || {}).title || ''} {...((props['tabs-props'] || {})[index] || {})}{...a11yProps(index)} />
                                    ))}
                                </Tabs>}
                            <Box key={2}>{props['children-right']}</Box>
                        </Toolbar>
                    </AppBar>
                    {props['disable-drawer'] ? null :
                        <Drawer variant="permanent" open={open}>
                            <DrawerHeader>
                                <IconButton onClick={handleDrawerClose}>
                                    {theme.direction === 'rtl' ?
                                        <ChevronRightIcon/> :
                                        <ChevronLeftIcon/>}
                                </IconButton>
                            </DrawerHeader>
                            <Divider/>
                            <List>
                                {isEnabled && props['disable-fullscreen'] ? null :
                                    <Tooltip
                                        title={'Enable/Disable fullscreen'}
                                        arrow
                                        placement="right" {...props['props-tooltip-fullscreen']}>
                                        <ListItem key={'fullscreen'}
                                                  disablePadding>
                                            <ListItemButton
                                                sx={{
                                                    minHeight: 48,
                                                    justifyContent: open ? 'initial' : 'center',
                                                    px: 2.5,
                                                }}
                                                onClick={onToggle}
                                                {...props['props-fullscreen']}
                                            >
                                                <ListItemIcon
                                                    sx={{
                                                        minWidth: 0,
                                                        mr: open ? 3 : 'auto',
                                                        justifyContent: 'center',
                                                    }}
                                                >
                                                    {fullScreen ?
                                                        <FullscreenExitIcon/> :
                                                        <FullscreenIcon/>}
                                                </ListItemIcon>
                                                <ListItemText
                                                    primary={'FULLSCREEN'}
                                                    sx={{opacity: open ? 1 : 0}}/>
                                            </ListItemButton>
                                        </ListItem></Tooltip>}
                                {props['disable-run'] ? null :
                                    <Tooltip
                                        title={'Run current data'}
                                        arrow
                                        placement="right" {...props['props-tooltip-run']}>
                                        <ListItem key={'run'} disablePadding>
                                            <ListItemButton
                                                component={'button'}
                                                type="submit"
                                                sx={{
                                                    minHeight: 48,
                                                    justifyContent: open ? 'initial' : 'center',
                                                    px: 2.5,
                                                }}
                                                {...props['props-run']}
                                            >
                                                <ListItemIcon
                                                    sx={{
                                                        minWidth: 0,
                                                        mr: open ? 3 : 'auto',
                                                        justifyContent: 'center',
                                                    }}
                                                >
                                                    <PlayCircleIcon/>
                                                </ListItemIcon>
                                                <ListItemText primary={'RUN'}
                                                              sx={{opacity: open ? 1 : 0}}/>
                                            </ListItemButton>
                                        </ListItem></Tooltip>}
                                {props['disable-upload'] ? null :
                                    <Tooltip
                                        title={'Upload data'}
                                        arrow
                                        placement="right" {...props['props-tooltip-upload']}>
                                        <ListItem key={'upload'} disablePadding>
                                            <ListItemButton
                                                component={'label'}
                                                sx={{
                                                    minHeight: 48,
                                                    justifyContent: open ? 'initial' : 'center',
                                                    px: 2.5,
                                                }}
                                                {...props['props-upload']}
                                            >
                                                <ListItemIcon
                                                    sx={{
                                                        minWidth: 0,
                                                        mr: open ? 3 : 'auto',
                                                        justifyContent: 'center',
                                                    }}
                                                >
                                                    <FileUploadOutlinedIcon/>
                                                </ListItemIcon>
                                                <ListItemText primary={'UPLOAD'}
                                                              sx={{opacity: open ? 1 : 0}}/>

                                                <input accept={['json']}
                                                       type={'file'}
                                                       hidden
                                                       onChange={upload}></input>
                                            </ListItemButton>
                                        </ListItem></Tooltip>}
                                {props['disable-download'] ? null :
                                    <Tooltip
                                        title={'Download current data'}
                                        arrow
                                        placement="right" {...props['props-tooltip-download']}>
                                        <ListItem key={'download'}
                                                  disablePadding>
                                            <ListItemButton
                                                sx={{
                                                    minHeight: 48,
                                                    justifyContent: open ? 'initial' : 'center',
                                                    px: 2.5
                                                }}
                                                onClick={() => {
                                                    exportJson({
                                                        data: props.context.props.formData,
                                                        fileName: `${props.context.props.name || 'file'}.json`
                                                    })
                                                }}
                                                {...props['props-download']}
                                            >
                                                <ListItemIcon
                                                    sx={{
                                                        minWidth: 0,
                                                        mr: open ? 3 : 'auto',
                                                        justifyContent: 'center',
                                                    }}
                                                >
                                                    <FileDownloadOutlinedIcon/>
                                                </ListItemIcon>
                                                <ListItemText
                                                    primary={'DOWNLOAD'}
                                                    sx={{opacity: open ? 1 : 0}}/>
                                            </ListItemButton>
                                        </ListItem>
                                    </Tooltip>}
                                {props['disable-datasaver'] ? null :
                                    <Tooltip
                                        title={(savingData ? 'Saving' : 'Save') + ' data on the sessionStorage of the browser'}
                                        arrow
                                        placement="right" {...props['props-tooltip-datasaver']}>
                                        <ListItem key={'datasaver'}
                                                  disablePadding>
                                            <ListItemButton
                                                component={'button'}
                                                sx={{
                                                    minHeight: 48,
                                                    justifyContent: open ? 'initial' : 'center',
                                                    px: 2.5
                                                }}
                                                onClick={() => {
                                                    setSavingData(!savingData)
                                                }}
                                                {...props['props-datasaver']}
                                            >
                                                <ListItemIcon
                                                    sx={{
                                                        minWidth: 0,
                                                        mr: open ? 3 : 'auto',
                                                        justifyContent: 'center',
                                                    }}
                                                >
                                                    {savingData ?
                                                        <DataSaverOnIcon/> :
                                                        <DataSaverOffIcon/>}
                                                </ListItemIcon>
                                                <ListItemText
                                                    primary={'DATASAVER'}
                                                    sx={{opacity: open ? 1 : 0}}/>
                                            </ListItemButton>
                                        </ListItem></Tooltip>}
                                {props['disable-restore'] ? null :
                                    <Tooltip
                                        title={'Restore data'}
                                        arrow
                                        placement="right" {...props['props-tooltip-restore']}>
                                        <ListItem key={'restore'}
                                                  disablePadding>
                                            <ListItemButton
                                                component={'label'}
                                                sx={{
                                                    minHeight: 48,
                                                    justifyContent: open ? 'initial' : 'center',
                                                    px: 2.5,
                                                }}
                                                onClick={() => {
                                                    setOpenRestore(true)
                                                }}
                                                {...props['props-restore']}
                                            >
                                                <ListItemIcon
                                                    sx={{
                                                        minWidth: 0,
                                                        mr: open ? 3 : 'auto',
                                                        justifyContent: 'center',
                                                    }}
                                                >
                                                    <RestoreIcon/>
                                                </ListItemIcon>
                                                <ListItemText
                                                    primary={'RESTORE DATA'}
                                                    sx={{opacity: open ? 1 : 0}}/>
                                            </ListItemButton>
                                        </ListItem>
                                    </Tooltip>}
                                {props['disable-delete'] ? null :
                                    <Tooltip
                                        title={'Cleanup current data'}
                                        arrow
                                        placement="right" {...props['props-tooltip-delete']}>
                                        <ListItem key={'delete'} disablePadding>
                                            <ListItemButton
                                                component={'label'}
                                                sx={{
                                                    minHeight: 48,
                                                    justifyContent: open ? 'initial' : 'center',
                                                    px: 2.5,
                                                }}
                                                onClick={() => {
                                                    props.context.props.onChange({})
                                                }}
                                                {...props['props-delete']}
                                            >
                                                <ListItemIcon
                                                    sx={{
                                                        minWidth: 0,
                                                        mr: open ? 3 : 'auto',
                                                        justifyContent: 'center',
                                                    }}
                                                >
                                                    <CancelIcon/>
                                                </ListItemIcon>
                                                <ListItemText primary={'CLEAN'}
                                                              sx={{opacity: open ? 1 : 0}}/>
                                            </ListItemButton>
                                        </ListItem>
                                    </Tooltip>}
                            </List>
                        </Drawer>}
                    <Box component="main" sx={{
                        flexGrow: 1,
                        py: 3,
                        pl: 3,
                        pr: '67px'
                    }} {...props['props-main']}>
                        <DrawerHeader/>
                        {anchor}
                        {props.children.map((element, index) => (
                            Math.abs(value) === index ? element : null
                        ))}
                    </Box>
                    <ScrollTop anchor={anchor}>
                        <Fab size="small" aria-label="scroll back to top">
                            <KeyboardArrowUpIcon/>
                        </Fab>
                    </ScrollTop>
                    <Dialog fullWidth
                            maxWidth="sm" scroll={'paper'} onClose={() => {
                        setOpenRestore(false);
                    }} open={openRestore}>
                        <DialogTitle>Restore data</DialogTitle>
                        <DialogContent dividers={true}>
                            <List sx={{pt: 0}}>
                                {!openRestore ? null : JSON.parse(window.sessionStorage.getItem(key) || '[]').reverse().map((raw, i, array) => (
                                    ((i === 0 && dataHash !== raw[3]) || (i !== 0 && array[i - 1][3] !== raw[3])) ?
                                        <ListItem
                                            key={i}
                                            secondaryAction={
                                                <IconButton onClick={() => {
                                                    setOldValue(raw)
                                                    setOpenDiff(true)
                                                }}>
                                                    <Tooltip
                                                        title={'Show data difference'}
                                                        arrow
                                                        placement="left">
                                                        <DifferenceIcon/></Tooltip>
                                                </IconButton>
                                            }>
                                            <ListItemAvatar
                                                sx={{cursor: 'pointer'}}
                                                onClick={() => {
                                                    setOpenRestore(false);
                                                    props.context.props.onChange(raw[0])
                                                }}>
                                                <Tooltip
                                                    title={'Restore data'}
                                                    arrow
                                                    placement="right">
                                                    <Avatar>
                                                        <ReplayIcon/>
                                                    </Avatar></Tooltip>
                                            </ListItemAvatar>
                                            <ListItemText
                                                primary={(new Date(raw[2] * 60000)).toLocaleString()}
                                            />
                                        </ListItem> : null
                                ))}
                                <Dialog scroll={'paper'} open={openDiff}
                                        onClose={handleDiffClose} fullWidth
                                        maxWidth={"xl"}>
                                    <DialogTitle>Show difference</DialogTitle>
                                    <DialogContent dividers={true}>
                                        {oldValue ? <ReactDiffViewer
                                            rightTitle={(new Date(Math.floor(Date.now() / 60000) * 60000)).toLocaleString() + ' (current)'}
                                            leftTitle={(new Date(oldValue[2] * 60000)).toLocaleString()}
                                            oldValue={JSON.stringify(oldValue[0], null, 2)}
                                            newValue={JSON.stringify(props.context.props.formData, null, 2)}/> : null}
                                    </DialogContent>
                                    <DialogActions>
                                        <Button onClick={() => {
                                            setOpenRestore(false);
                                            props.context.props.onChange(oldValue[0])
                                            handleDiffClose()
                                        }}>Restore</Button>
                                        <Button
                                            onClick={handleDiffClose}>Close</Button>
                                    </DialogActions>
                                </Dialog>
                            </List>
                        </DialogContent>
                        <DialogActions>
                            <Button onClick={() => {
                                setOpenRestore(false);
                                window.sessionStorage.removeItem(key)
                            }}>Erase storage</Button>
                            <Button
                                onClick={() => {
                                    setOpenRestore(false);
                                }}>Close</Button>
                        </DialogActions>
                    </Dialog>
                </Box>
            )}
        </ReactFullscreen>
    );
}