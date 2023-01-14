import React, {useEffect, Suspense} from 'react';
import {diff, applyChange} from 'deep-diff';
import cjson from 'compressed-json';
import cloneDeep from 'lodash/cloneDeep';
import PropTypes from 'prop-types';
import useScrollTrigger from '@mui/material/useScrollTrigger';
import {styled, useTheme} from '@mui/material/styles';
import {exportJson} from './io';
import {useFullscreen} from 'ahooks';
import hash from 'object-hash'
import DiffViewer from './diff';

const Toolbar = React.lazy(() => import('@mui/material/Toolbar'));
const Box = React.lazy(() => import('@mui/material/Box'));
const Fade = React.lazy(() => import('@mui/material/Fade'));
const Fab = React.lazy(() => import('@mui/material/Fab'));
const KeyboardArrowUpIcon = React.lazy(() => import('@mui/icons-material/KeyboardArrowUp'));
const Tabs = React.lazy(() => import('@mui/material/Tabs'));
const Tab = React.lazy(() => import('@mui/material/Tab'));
const MuiDrawer = React.lazy(() => import('@mui/material/Drawer'));
const MuiAppBar = React.lazy(() => import('@mui/material/AppBar'));
const List = React.lazy(() => import('@mui/material/List'));
const CssBaseline = React.lazy(() => import('@mui/material/CssBaseline'));
const Divider = React.lazy(() => import('@mui/material/Divider'));
const IconButton = React.lazy(() => import('@mui/material/IconButton'));
const MenuIcon = React.lazy(() => import('@mui/icons-material/Menu'));
const ChevronLeftIcon = React.lazy(() => import('@mui/icons-material/ChevronLeft'));
const ChevronRightIcon = React.lazy(() => import('@mui/icons-material/ChevronRight'));
const ListItem = React.lazy(() => import('@mui/material/ListItem'));
const ListItemButton = React.lazy(() => import('@mui/material/ListItemButton'));
const ListItemIcon = React.lazy(() => import('@mui/material/ListItemIcon'));
const ListItemText = React.lazy(() => import('@mui/material/ListItemText'));
const ListItemAvatar = React.lazy(() => import('@mui/material/ListItemAvatar'));
const Avatar = React.lazy(() => import('@mui/material/Avatar'));
const FileDownloadOutlinedIcon = React.lazy(() => import('@mui/icons-material/FileDownloadOutlined'));
const FileUploadOutlinedIcon = React.lazy(() => import('@mui/icons-material/FileUploadOutlined'));
const PlayCircleIcon = React.lazy(() => import('@mui/icons-material/PlayCircle'));
const Tooltip = React.lazy(() => import('@mui/material/Tooltip'));
const FullscreenIcon = React.lazy(() => import('@mui/icons-material/Fullscreen'));
const FullscreenExitIcon = React.lazy(() => import('@mui/icons-material/FullscreenExit'));
const DataSaverOnIcon = React.lazy(() => import('@mui/icons-material/DataSaverOn'));
const DataSaverOffIcon = React.lazy(() => import('@mui/icons-material/DataSaverOff'));
const RestoreIcon = React.lazy(() => import('@mui/icons-material/Restore'));
const DifferenceIcon = React.lazy(() => import('@mui/icons-material/Difference'));
const DialogTitle = React.lazy(() => import('@mui/material/DialogTitle'));
const Dialog = React.lazy(() => import('@mui/material/Dialog'));
const DialogContent = React.lazy(() => import('@mui/material/DialogContent'));
const DialogActions = React.lazy(() => import('@mui/material/DialogActions'));
const Button = React.lazy(() => import('@mui/material/Button'));
const ReplayIcon = React.lazy(() => import('@mui/icons-material/Replay'));
const CancelIcon = React.lazy(() => import('@mui/icons-material/Cancel'));
const AdbIcon = React.lazy(() => import('@mui/icons-material/Adb'));


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
        anchor.current.scrollIntoView({
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
const applyChanges = (target, changes) => {
    changes.forEach((change) => applyChange(target, null, change))
    return target
}
const buildData = (changes, currentDate) => {
    changes = changes.filter(
        ([date, data], i) => (i === 0 || date <= currentDate)
    )
    return changes.slice(1).reduce(
        (target, [date, data]) => applyChanges(target, data),
        cloneDeep(changes[0][1])
    )
}

const readStoredData = (key, dataHash) => {
    let storage = (window.sessionStorage.getItem(key) || ''),
        changes = storage.slice(28), getData;
    changes = (changes ? cjson.decompress.fromString(changes) : [])
    getData = buildData.bind(null, changes)
    if (storage.slice(0, 28) === dataHash) {
        changes = changes.slice(0, changes.length - 1)
    }
    return changes.map((
        [date, data, oldHash]
    ) => ([date, getData, dataHash === oldHash]))
}

const appendData = (key, formData) => {
    let dataHash = hash(formData, {
            'algorithm': 'sha1',
            'encoding': 'base64'
        }),
        storage = window.sessionStorage.getItem(key) || '';

    if (storage.slice(0, 28) !== dataHash) {
        let data, changes = storage.slice(28);
        changes = changes ? cjson.decompress.fromString(changes) : [];
        let currentDate = Math.floor(Date.now() / 60000);
        changes = changes.filter(
            ([date, data], i) => (date < currentDate)
        )
        if (changes.length) {
            data = diff(changes.slice(1).reduce(
                (target, [date, data]) => applyChanges(target, data),
                cloneDeep(changes[0][1])
            ), formData)
            if (!data) {
                return
            }
        } else {
            data = formData
        }
        changes.push([currentDate, data, dataHash])

        window.sessionStorage.setItem(
            key, `${dataHash}${cjson.compress.toString(changes)}`
        );

    }
}
export default function _nav(props) {
    const [savingData, setSavingData] = React.useState(props.hasOwnProperty('savingData') ? props.savingData : true);
    const [value, setValue] = React.useState(props.current_tab || 0);
    const handleChange = (event, newValue) => {
        setValue(newValue);
    };
    const theme = useTheme();
    const [open, setOpen] = React.useState(false);
    let key = 'schedula-' + props.context.props.formContext.$id + '-' + props.context.props.idSchema.$id + '-formData';
    let formData = props.context.props.formData;
    useEffect(function updateStorage() {
        if (savingData) {
            try {
                appendData(key, formData)
            } catch (error) {
                setSavingData(false)
                alert(`Ops..${savingData} disabling auto-saving because:\n\n${error.message}`)
            }
        }
    }, [key, formData, savingData]);


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
    const anchor = React.useRef(null);
    const [isFullscreen, {isEnabled, toggleFullscreen}] = useFullscreen(
        props.context.props.formContext.ref
    );
    return (<Suspense>
        <Box sx={{display: 'flex'}}>
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
                        {!isEnabled || props['disable-fullscreen'] ? null :
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
                                        onClick={toggleFullscreen}
                                        {...props['props-fullscreen']}
                                    >
                                        <ListItemIcon
                                            sx={{
                                                minWidth: 0,
                                                mr: open ? 3 : 'auto',
                                                justifyContent: 'center',
                                            }}
                                        >
                                            {isFullscreen ?
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
                                        formMethod="POST"
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
                        {props['disable-debug'] ? null :
                            <Tooltip
                                title={'Debug current data'}
                                arrow
                                placement="right" {...props['props-tooltip-debug']}>
                                <ListItem key={'debug'} disablePadding>
                                    <ListItemButton
                                        component={'button'}
                                        type="submit"
                                        formMethod="POST"
                                        headers={JSON.stringify({'Debug': 'true'})}
                                        sx={{
                                            minHeight: 48,
                                            justifyContent: open ? 'initial' : 'center',
                                            px: 2.5,
                                        }}
                                        {...props['props-debug']}
                                    >
                                        <ListItemIcon
                                            sx={{
                                                minWidth: 0,
                                                mr: open ? 3 : 'auto',
                                                justifyContent: 'center',
                                            }}
                                        >
                                            <AdbIcon/>
                                        </ListItemIcon>
                                        <ListItemText primary={'DEBUG'}
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
                                title={(savingData ? 'Stop saving' : 'Save') + ' data on the sessionStorage of the browser'}
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
                bgcolor: 'background.paper',
                flexGrow: 1,
                py: 3,
                pl: 3,
                pr: '67px'
            }} {...props['props-main']}>
                <DrawerHeader/>
                <div ref={anchor}/>
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
                        {!openRestore ? null : readStoredData(key, dataHash).reverse().map(([date, getD, same], i) => (
                            <ListItem
                                key={i}
                                secondaryAction={
                                    !same ? <IconButton onClick={() => {
                                        setOldValue([date, getD(date)])
                                        setOpenDiff(true)
                                    }}>
                                        <Tooltip
                                            title={'Show data difference'}
                                            arrow
                                            placement="left">
                                            <DifferenceIcon/></Tooltip>
                                    </IconButton> : null
                                }>
                                <ListItemAvatar
                                    sx={{cursor: 'pointer'}}
                                    onClick={() => {
                                        setOpenRestore(false);
                                        props.context.props.onChange(getD(date))
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
                                    primary={(new Date(date * 60000)).toLocaleString()}
                                />
                            </ListItem>
                        ))}
                        <Dialog scroll={'paper'} open={openDiff}
                                onClose={handleDiffClose} fullWidth
                                maxWidth={"xl"}>
                            <DialogTitle>Show difference</DialogTitle>
                            <DialogContent dividers={true}>
                                {oldValue ? <DiffViewer
                                    rightTitle={(new Date(Math.floor(Date.now() / 60000) * 60000)).toLocaleString() + ' (current)'}
                                    leftTitle={(new Date(oldValue[0] * 60000)).toLocaleString()}
                                    oldValue={JSON.stringify(oldValue[1], null, 2)}
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
    </Suspense>);
}