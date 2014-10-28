#!/usr/bin/env python
import requests as req
from PIL import Image
from subprocess import call
from random import randint
from os.path import isfile
import os, sys, string, random, argparse, ConfigParser

Config = ConfigParser.ConfigParser()
Config.read('conf.ini')

def configmap(section):
    dict1 = {}
    options = Config.options(section)
    for option in options:
        try:
            dict1[option] = Config.get(section, option)
            if dict1[option] == -1:
                DebugPrint("skip: %s" % option)
        except:
            print("exception on %s!" % option)
            dict1[option] = None
    return dict1

def filelen(infile):
    with open(infile) as f:
        for i, l in enumerate(f):
            pass
        return i + 1

def save_file_url(url):
    try:
        filename = url.split('/')[-1]
    except IndexError:
        print "doesn't seem to be either a local file or a url..."
        return
    response = req.get(url)
    if response.status_code == 200 or 304:
        img_file = open(filename, 'wb')
        img_file.write(response.content)
        img_file.close()
        print "\nfetched image file %s" % filename
        return filename
    else:
        print "Bad response (%s) from server for this URL" % response.status_code

def handle_options():
    defaults = configmap('Defaults')
    parser = argparse.ArgumentParser()

    parser.add_argument("input_file")
    parser.add_argument("-f", "--frames", default=defaults['animation_frames'],
        type=int, help="Number of frames for the animation")
    parser.add_argument("-d", "--delay", default=defaults['animation_delay'],
        type=int, help="animation delay in 100ths of a second")
    parser.add_argument("-a", "--amount", default=defaults['glitch_amount'],
        type=int, help="Text glitches per frame")
    parser.add_argument("-s", "--saturation", default=defaults['saturation'],
        type=int, help="Saturation change (100 is unchanged)")
    parser.add_argument("-c", "--colors", default=defaults['colors'],
        type=int, help="Number of colors in the color pallete of the final GIF")
    parser.add_argument("-r", "--rotate", default=defaults['rotation_chance'], 
        type=int, help="Chance of image rotation")
    parser.add_argument("-i", "--interactive", default=False, 
        type=int, help="Turn on prompt-based interface")

    opts = parser.parse_args()

    if not isfile(opts.input_file):                           # if we don't find it,
        opts.input_file = save_file_url(opts.input_file)      # assume it's a URL
    
    return opts
    

def convertbmp(infile, outfile):
    outfile = outfile.split('.')[0] + '.bmp'
    image = Image.open(infile)
    try:
        image.save(outfile, 'BMP')
        return outfile
    except IOError:
        return ("Cannot process", infile)

class Gifscythe():                                 # methods using Gifsicle
    
    def finalize(self, input_gif):
        print 'Optimizing and dithering final GIF...'
        call('gifsicle -O3 --colors %i --dither --batch %s' % (opts.colors, input_gif), shell=True)

class ImageMage():                                 # handles ImageMagick-based glitches
   
    # randomize saturation and hue with a range 
    def color_jitter(self, filename, hue_range):
        frame_saturation = opts.saturation + randint(-15,35)
        hue = randint(100-hue_range, 100+hue_range)
        IM_command = "mogrify -quiet -modulate 100,%i,%i %s" % (frame_saturation, hue, filename)
        call(IM_command, shell=True)

    # randomize brightness to create flashing effect, accents lines nicely
    def flashing_lights(self, filename, light_range):
        light = randint(110-light_range/2, 110+light_range)
        IM_command = "mogrify -quiet -modulate %i,100,100 %s" % (light, filename)
        call(IM_command, shell=True)
    
    # should be used BEFORE text-based glitches if you want non-horizontal glitches
    def random_rotate(self, filename, chance):
        if chance > 100: 
            chance = 100
        elif chance <= 0:
            return
        if randint(1,100) <= chance:
            IM_command = "mogrify -quiet -transpose %s" % filename
            call(IM_command, shell=True)
            return True
        else:
            return False

    # realign images rotated with the above function        
    def unrotate(self, filename):
        IM_command = "mogrify -quiet -rotate 270 %s" % filename
        call(IM_command, shell=True)
            
            

class SedSorceror():                               # handles sed-based effects

    def __init__(self, image):
        self.filelength = filelen(image)
        print ("File length is %s lines" % self.filelength)
        #basic implementation of the config file below
        #we can discuss which params we want to offload to the ini file later
        self.headerdifferential = configmap('Settings')['headerdifferential']
        self.endheader = int(self.filelength * float(self.headerdifferential)) + 2
        if self.endheader > 200:
            self.endheader =200
        print "End of header approximated at line %s" % self.endheader

    def rgb_wiggle(self, filename, outfile, cutcount):
        targets = [''.join(random.choice(string.hexdigits) for n in range(0,2)) for n in range (0,30)]
        for i in range(cutcount):
            target = random.choice(targets)
            start = randint(self.endheader, int(self.filelength * 0.90))

            if randint(0,100) > 66:
                end = "$" # end of file
            else:
                end = str(randint(start + 1, self.filelength))

            payload = ''.join(random.choice(string.hexdigits) for i in range(randint(0,12)))
            
            if i == 0:
                sedcommand = "sed '%i,%s s/%s/%s/g' %s > %s" % (start, end, target, payload, filename, outfile)
            else:
                sedcommand = "sed -i '%i,%s s/%s/%s/g' %s" % (start, end, target, payload, filename)
            
            print "On lines %s through line %s, '%s' will be replaced with '%s'" % (start, end, target, payload)
            call(sedcommand, shell=True)
            filename = outfile

    # makes viewable BMPs but both PIL and Imagemagick seem to think they're broken
    def del_chunks(self, filename, outfile, chunkcount):
        for i in range(chunkcount):
            start = randint(self.endheader+100, int(self.filelength * 0.90))
            end = randint(start + 1, start+40)
            if i == 0:
                sedcommand = "sed -e '%i,%id' %s > %s" % (start, end, filename, outfile)
            else:
                sedcommand = "sed -i -e '%i,%id' %s" % (start, end, outfile)
            print sedcommand
            call(sedcommand, shell=True)

def glitchbmp(infile, outfile, amount):
    """
    infile is an image file
    outfile is the name of the bent output file (can include .bmp or be a single word)
    """
    outfile = outfile.split('.')[0] + '.bmp'

    sed = SedSorceror(infile)
    mage = ImageMage()
    
    rotated = mage.random_rotate(infile, opts.rotate)
    sed.rgb_wiggle(infile, outfile, amount)
    if rotated:
        print "File was rotated, trying to unrotate %s ..." % outfile
        mage.unrotate(outfile)
        mage.unrotate(infile)

    mage.color_jitter(outfile, randint(10,30))
    mage.flashing_lights(outfile, randint(10,40))

    return outfile


def animateglitch(infile, frames, anim_delay, glitch_amount):

    convertedimage = convertbmp(infile, 'converted-%s' % infile)
    print "%s converted to %s \n" % (infile, convertedimage)
    
    i = 1
    while i <= frames:
        glitchedimage = glitchbmp(convertedimage, 'glitched-' + infile.split('.')[0] + str(i) + '.bmp', glitch_amount)
        print "%s glitched to %s \n" % (convertedimage, glitchedimage)
        print "----------------------------------------"
        i += 1

    gif = Gifscythe()
    print "\nAnimating GIF... (this may take a while)"
    filename_base = infile.split('.')[0]
    animatecommand = "convert -delay %i -loop 0 -quiet glitched*bmp %s-animated.gif" % (anim_delay, filename_base)
    call(animatecommand, shell=True)
    gif.finalize("%s-animated.gif" % filename_base)
    
    print "Done! Cleaning up...."
    call("rm glitch*.bmp convert*.bmp", shell=True)


opts = handle_options()
animateglitch(opts.input_file, opts.frames, opts.delay, opts.amount)

