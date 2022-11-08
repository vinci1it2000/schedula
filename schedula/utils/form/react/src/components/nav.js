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
import FileDownloadOutlinedIcon from '@mui/icons-material/FileDownloadOutlined';
import FileUploadOutlinedIcon from '@mui/icons-material/FileUploadOutlined';
import PlayCircleIcon from '@mui/icons-material/PlayCircle';
import {exportJson} from './io';
import {FullScreen, useFullScreenHandle} from "react-full-screen";
import FullscreenIcon from '@mui/icons-material/Fullscreen';
import FullscreenExitIcon from '@mui/icons-material/FullscreenExit';

function ScrollTop(props) {
    const {children, window} = props;
    // Note that you normally won't need to set the window ref as useScrollTrigger
    // will default to window.
    // This is only being set here because the demo is in an iframe.
    const trigger = useScrollTrigger({
        target: window ? window() : undefined,
        disableHysteresis: true,
        threshold: 100,
    });

    const handleClick = (event) => {
        const anchor = (event.target.ownerDocument || document).querySelector(
            '#back-to-top-anchor',
        );

        if (anchor) {
            anchor.scrollIntoView({
                block: 'center',
            });
        }
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
export default function _nav(props) {
    const [value, setValue] = React.useState(props.current_tab || 0);
    const handleChange = (event, newValue) => {
        setValue(newValue);
    };
    const theme = useTheme();
    const [open, setOpen] = React.useState(false);

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
    const handle = useFullScreenHandle();

    return (
        <FullScreen handle={handle}>
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
                        {props['disable-fullscreen'] ? null :
                            <IconButton onClick={handle.enter}>{
                                handle.active ?
                                    <FullscreenExitIcon/> : <FullscreenIcon/>
                            }</IconButton>}
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
                            {props['disable-run'] ? null :
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
                                </ListItem>}
                            {props['disable-upload'] ? null :
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

                                        <input accept={['json']} type={'file'}
                                               hidden
                                               onChange={upload}></input>
                                    </ListItemButton>
                                </ListItem>}
                            {props['disable-download'] ? null :
                                <ListItem key={'download'} disablePadding>
                                    <ListItemButton
                                        sx={{
                                            minHeight: 48,
                                            justifyContent: open ? 'initial' : 'center',
                                            px: 2.5,
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
                                        <ListItemText primary={'DOWNLOAD'}
                                                      sx={{opacity: open ? 1 : 0}}/>
                                    </ListItemButton>
                                </ListItem>}
                        </List>
                    </Drawer>}
                <Box component="main" sx={{
                    flexGrow: 1,
                    py: 3,
                    pl: 3,
                    pr: '67px'
                }} {...props['props-main']}>
                    <DrawerHeader/>
                    <div id="back-to-top-anchor"/>
                    {props.children.map((element, index) => (
                        Math.abs(value) === index ? element : null
                    ))}
                </Box>
                <ScrollTop>
                    <Fab size="small" aria-label="scroll back to top">
                        <KeyboardArrowUpIcon/>
                    </Fab>
                </ScrollTop>
            </Box>
        </FullScreen>
    );
}